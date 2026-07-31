"""
담당자별 Task 리포트를 메일로 발송한다.

- 일반 담당자(Bryan / Eric / Alex / Michael / Hailey): 자기 것만 받음
- 관리자(Calvin / Jaehyun): 전원(모든 사람)의 개별 테이블을 모두 받음

준비: config.py(로컬은 local_settings.py, CI는 GitHub Secrets)에서
  SMTP_USER / SMTP_PASSWORD / RECIPIENTS[...] 를 채워 넣으세요.

사용법:
  python send_reports.py            # 미리보기(발송 안 함). *.html 파일로 저장
  python send_reports.py --send     # 실제 메일 발송
"""

import re
import sys
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

import config
import people_projects as pp

TASK_DB = "32b5658a-871f-814f-824a-ceafe15f89dc"
TASK_LOG_DB = "32b5658a-871f-81b7-884b-db05bc08e5b3"   # Task Log_DB (Task 의 'task log_DB' relation 대상)

# Task 당 표에 보여줄 최근 작업로그 개수
LOG_LIMIT = 3

# 마감일이 이 일수 이하로 남으면(=지난 경우 포함) 표에서 빨갛게 강조
DUE_SOON_DAYS = 3

# 이 상태인 Task 는 표에서 아예 제외 (Complete 그룹은 '완료' 하나뿐)
DONE_STATUS = "완료"

# CI(GitHub Actions)는 UTC 로 도므로 '오늘' 은 한국시간 기준으로 계산한다
KST = timezone(timedelta(hours=9))

# 표시이름 -> 담당자 매칭 키워드(소문자)
PEOPLE = [
    ("Bryan", "bryan"),
    ("Eric", "eric"),
    ("Alex", "alex"),
    ("Michael", "michael"),
    ("Hailey", "hailey"),
    ("Trisha", "trisha"),
    ("Calvin", "calvin"),
    ("Jason", "jason"),
]

# 관리자: 전원의 개별 테이블을 모두 받는 사람
MANAGERS = {"Calvin", "Jason"}

# 관리자 리포트에 넣을 개별 섹션 대상 (실무 담당자들. Jason 은 담당 데이터가 없어 제외)
AGGREGATE_FOR_MANAGERS = ["Bryan", "Eric", "Alex", "Michael", "Hailey", "Trisha", "Calvin"]

# Task 표: Notion 속성에서 그대로 가져오는 컬럼 + 마지막에 작업로그 컬럼을 덧붙인다
TASK_COLUMNS = ["작업명", "상태", "담당자", "마감일", "project_DB"]
TASK_HEADERS = [
    "작업명", "상태", "담당자", "마감일", "소속 프로젝트",
    f"최근 작업로그 (최신 {LOG_LIMIT})",
]


# ----------------------------------------------------------------------
# 데이터
# ----------------------------------------------------------------------
def drop_done(rows):
    """상태가 '완료' 인 행을 제외한다."""
    kept = []
    for r in rows:
        v = r.get("properties", {}).get("상태") or {}
        st = v.get("status") or {}
        if st.get("name") != DONE_STATUS:
            kept.append(r)
    return kept


def filter_by_person(rows, keyword):
    return [
        r
        for r in rows
        if any(keyword in n.lower() for n in pp.people_names(r["properties"]))
    ]


# ----------------------------------------------------------------------
# 마감일 임박 판정
# ----------------------------------------------------------------------
def days_left(row):
    """마감일까지 남은 일수(한국시간 기준). 마감일이 없으면 None."""
    v = row.get("properties", {}).get("마감일")
    if not v or v.get("type") != "date" or not v.get("date"):
        return None
    # 기간이면 끝나는 날이 실제 마감일
    raw = v["date"].get("end") or v["date"].get("start")
    if not raw:
        return None
    try:
        due = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    due = due.astimezone(KST).date() if due.tzinfo else due.date()
    return (due - datetime.now(KST).date()).days


def urgent_flags(rows):
    """행별로 '마감 임박(D-3 이하)' 여부. 마감일 없는 행은 False."""
    flags = []
    for r in rows:
        d = days_left(r)
        flags.append(d is not None and d <= DUE_SOON_DAYS)
    return flags


# ----------------------------------------------------------------------
# Task 작업로그 (Task Log_DB)
# ----------------------------------------------------------------------
# 로그 본문은 "2026/06/02 09:55 검사검수신청서 제출" 처럼 날짜가 앞에 붙어 있다.
_LOG_DATE_RE = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})")


def _rich_text(prop):
    if not prop:
        return []
    return prop.get(prop.get("type", ""), []) or []


def parse_log(row):
    """Task Log_DB 한 행 -> {title, sort}. 제목은 "날짜@작성자 내용" 구조."""
    props = row.get("properties", {})
    title = "".join(x.get("plain_text", "") for x in _rich_text(props.get("이름"))).strip()

    # 정렬은 제목 앞의 날짜 기준, 없으면 생성 일시로 대체
    m = _LOG_DATE_RE.search(title)
    if m:
        y, mo, d, h, mi = (int(g) for g in m.groups())
        sort = f"{y:04d}{mo:02d}{d:02d}{h:02d}{mi:02d}"
    else:
        sort = re.sub(r"\D", "", props.get("생성 일시", {}).get("created_time", "") or "")[:12]

    return {"title": title, "sort": sort}


def build_log_index(log_rows):
    """{task_page_id: [로그 최신순]} 인덱스. 로그 DB 를 한 번만 읽어서 만든다."""
    index = {}
    for row in log_rows:
        entry = parse_log(row)
        for rel in row.get("properties", {}).get("task_DB", {}).get("relation", []):
            index.setdefault(rel["id"], []).append(entry)
    for entries in index.values():
        entries.sort(key=lambda e: e["sort"], reverse=True)
    return index


def task_matrix(tasks, log_index):
    """Task 표 행렬. 마지막 컬럼에 최근 작업로그를 붙인다."""
    matrix = []
    for t in tasks:
        row = [pp.cell_value(t["properties"][c]) for c in TASK_COLUMNS]
        row.append(log_cell(log_index.get(t["id"], [])))
        matrix.append(row)
    return matrix


# ----------------------------------------------------------------------
# HTML 생성
# ----------------------------------------------------------------------
def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Html(str):
    """이미 이스케이프된 HTML 조각. 표에서 그대로 출력하고 줄바꿈을 허용한다."""


def log_cell(entries):
    """작업로그 제목을 한 줄씩 셀 하나에 담는다 (최신 LOG_LIMIT 개)."""
    if not entries:
        return Html('<span style="color:#bbb;">-</span>')
    lines = [
        f'<div style="margin:0 0 3px;">{_esc(e["title"])}</div>'
        for e in entries[:LOG_LIMIT]
    ]
    return Html("".join(lines))


def html_table(headers, matrix, urgent=None):
    """urgent: matrix 와 같은 길이의 bool 리스트. True 인 줄은 빨갛게 표시."""
    if not matrix:
        return '<p style="color:#888;">(항목 없음)</p>'
    th = "".join(
        f'<th style="border:1px solid #ddd;padding:6px 10px;background:#f4f4f4;'
        f'text-align:left;font-size:13px;">{_esc(h)}</th>'
        for h in headers
    )
    trs = []
    for i, row in enumerate(matrix):
        # 메일 클라이언트는 tr 배경/색 상속을 자주 무시하므로 td 마다 직접 넣는다
        hot = "background:#fdecea;color:#c0392b;font-weight:600;" if urgent and urgent[i] else ""
        tds = []
        for c in row:
            if isinstance(c, Html):
                tds.append(
                    f'<td style="border:1px solid #ddd;padding:6px 10px;font-size:13px;'
                    f'white-space:normal;min-width:280px;vertical-align:top;{hot}">{c}</td>'
                )
            else:
                tds.append(
                    f'<td style="border:1px solid #ddd;padding:6px 10px;font-size:13px;'
                    f'white-space:nowrap;vertical-align:top;{hot}">{_esc(c)}</td>'
                )
        trs.append(f"<tr>{''.join(tds)}</tr>")
    return (
        '<table style="border-collapse:collapse;border:1px solid #ddd;">'
        f"<thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"
    )


def person_section(name, tasks, log_index):
    """한 사람의 Task 표 (메일 안에 들어가는 조각)."""
    return f"""
  <h2 style="margin:26px 0 4px;border-bottom:2px solid #333;padding-bottom:4px;">{_esc(name)}</h2>
  <p style="color:#666;margin:0 0 10px;">담당 Task {len(tasks)}개</p>

  {html_table(TASK_HEADERS, task_matrix(tasks, log_index), urgent_flags(tasks))}
"""


def wrap_email(title, inner_html):
    return f"""\
<div style="font-family:'Malgun Gothic',AppleSDGothicNeo,sans-serif;color:#222;">
  <h1 style="margin:0 0 6px;font-size:20px;">{_esc(title)}</h1>
  {inner_html}
  <p style="color:#999;font-size:12px;margin-top:24px;">
    ※ <span style="color:#c0392b;font-weight:600;">빨간 줄</span>은 마감일이 {DUE_SOON_DAYS}일 이하로 남았거나 이미 지난 항목입니다.<br>
    ※ 이 메일은 Notion 데이터 기준 자동 생성되었습니다.
  </p>
</div>"""


# ----------------------------------------------------------------------
# 발송
# ----------------------------------------------------------------------
def send_mail(server, to_addr, subject, html):
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header(config.FROM_NAME, "utf-8")), config.SMTP_USER))
    msg["To"] = to_addr
    server.sendmail(config.SMTP_USER, [to_addr], msg.as_string())


def main():
    do_send = "--send" in sys.argv

    tasks_all = drop_done(pp.query_all(TASK_DB))
    log_index = build_log_index(pp.query_all(TASK_LOG_DB))

    # 1) 모든 사람의 데이터/섹션을 먼저 계산
    data = {}       # name -> tasks
    sections = {}   # name -> section html
    for name, keyword in PEOPLE:
        tasks = filter_by_person(tasks_all, keyword)
        data[name] = tasks
        sections[name] = person_section(name, tasks, log_index)

    # 실무 담당자 섹션을 이어붙인 관리자용 본문
    all_sections_html = "".join(sections[n] for n in AGGREGATE_FOR_MANAGERS)

    # 2) 수신자별 메일 구성
    reports = []  # (name, to_addr, subject, html, is_manager)
    for name, _ in PEOPLE:
        to_addr = config.RECIPIENTS.get(name, "").strip()
        is_manager = name in MANAGERS
        if is_manager:
            subject = f"[Task 리포트/관리자] 전체 담당자 현황 ({len(PEOPLE)}명)"
            html = wrap_email(f"{name}님 (관리자용) — 전체 담당자 Task", all_sections_html)
        else:
            subject = f"[Task 리포트] {name} — Task {len(data[name])}건"
            html = wrap_email(f"{name}님 Task 리포트", sections[name])
        reports.append((name, to_addr, subject, html, is_manager))

    # 3) 미리보기
    if not do_send:
        print("=== 미리보기 모드 (실제 발송 안 함) ===")
        for name, to_addr, subject, html, is_manager in reports:
            fname = f"report_{name}.html"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(html)
            tag = "관리자(전원)" if is_manager else "본인만"
            addr = to_addr or "(메일주소 미입력)"
            print(f"  {name} [{tag}] → {addr}   [{fname} 저장]")
        print("\n실제 발송하려면:  python send_reports.py --send")
        return

    # 4) 실제 발송
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        print("❌ SMTP_USER / SMTP_PASSWORD 를 먼저 채워주세요.")
        return

    print("SMTP 접속 중...")
    server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)
    try:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        for name, to_addr, subject, html, is_manager in reports:
            if not to_addr:
                print(f"  ⏭ {name}: 메일주소 미입력 → 건너뜀")
                continue
            send_mail(server, to_addr, subject, html)
            tag = "관리자(전원)" if is_manager else "본인만"
            print(f"  ✅ {name} [{tag}] → {to_addr} 발송 완료")
    finally:
        server.quit()
    print("완료.")


if __name__ == "__main__":
    main()
