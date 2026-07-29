"""
담당자별(Bryan / Eric / Alex / Michael) 프로젝트 & Task 리포트를
각자에게 개별 메일로 발송한다.

준비:
  config.py 에서
    - SMTP_USER / SMTP_PASSWORD (보내는 Gmail + 앱 비밀번호)
    - RECIPIENTS[...] 각 담당자 받는 메일 주소
  를 채워 넣으세요.

사용법:
  python send_reports.py            # 미리보기(발송 안 함). *.html 파일로 저장
  python send_reports.py --send     # 실제 메일 발송
"""

import sys
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

import bryan
import config
import people_projects as pp

PROJECT_DB = "32b5658a-871f-81f4-9daa-f918d575d389"
TASK_DB = "32b5658a-871f-814f-824a-ceafe15f89dc"

# 담당자 -> 담당자 매칭 키워드(소문자)
PEOPLE = [
    ("Bryan", "bryan"),
    ("Eric", "eric"),
    ("Alex", "alex"),
    ("Michael", "michael"),
    ("Calvin", "calvin"),
]

PROJECT_COLUMNS = [
    "프로젝트명", "상태", "담당자", "계약형태",
    "고객사", "공급사", "시작일", "마감일", "D-day", "지연사유",
]

TASK_COLUMNS = ["작업명", "상태", "담당자", "마감일", "project_DB", "지연 사유"]
TASK_HEADERS = ["작업명", "상태", "담당자", "마감일", "소속 프로젝트", "지연사유"]


# ----------------------------------------------------------------------
# 데이터
# ----------------------------------------------------------------------
def filter_by_person(rows, keyword):
    return [
        r
        for r in rows
        if any(keyword in n.lower() for n in pp.people_names(r["properties"]))
    ]


def rows_to_matrix(rows, columns):
    return [[pp.cell_value(r["properties"][c]) for c in columns] for r in rows]


# ----------------------------------------------------------------------
# HTML 생성
# ----------------------------------------------------------------------
def _esc(s):
    s = str(s)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def html_table(headers, matrix):
    if not matrix:
        return '<p style="color:#888;">(항목 없음)</p>'
    th = "".join(
        f'<th style="border:1px solid #ddd;padding:6px 10px;background:#f4f4f4;'
        f'text-align:left;font-size:13px;">{_esc(h)}</th>'
        for h in headers
    )
    trs = []
    for row in matrix:
        tds = "".join(
            f'<td style="border:1px solid #ddd;padding:6px 10px;font-size:13px;'
            f'white-space:nowrap;">{_esc(c)}</td>'
            for c in row
        )
        trs.append(f"<tr>{tds}</tr>")
    return (
        '<table style="border-collapse:collapse;border:1px solid #ddd;">'
        f"<thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"
    )


def build_email_html(name, projects, tasks):
    return f"""\
<div style="font-family:'Malgun Gothic',AppleSDGothicNeo,sans-serif;color:#222;">
  <h2 style="margin:0 0 4px;">{_esc(name)}님 프로젝트 &amp; Task 리포트</h2>
  <p style="color:#666;margin:0 0 16px;">담당 프로젝트 {len(projects)}개 · Task {len(tasks)}개</p>

  <h3 style="margin:18px 0 8px;">📁 프로젝트 ({len(projects)})</h3>
  {html_table(PROJECT_COLUMNS, rows_to_matrix(projects, PROJECT_COLUMNS))}

  <h3 style="margin:22px 0 8px;">✅ Task ({len(tasks)})</h3>
  {html_table(TASK_HEADERS, rows_to_matrix(tasks, TASK_COLUMNS))}

  <p style="color:#999;font-size:12px;margin-top:20px;">※ 이 메일은 Notion 데이터 기준 자동 생성되었습니다.</p>
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

    projects_all = pp.query_all(PROJECT_DB)
    tasks_all = pp.query_all(TASK_DB)

    # 사람별 리포트 준비
    reports = []
    for name, keyword in PEOPLE:
        projects = filter_by_person(projects_all, keyword)
        tasks = filter_by_person(tasks_all, keyword)
        html = build_email_html(name, projects, tasks)
        to_addr = config.RECIPIENTS.get(name, "").strip()
        reports.append((name, to_addr, projects, tasks, html))

    if not do_send:
        # 미리보기: html 파일로 저장
        print("=== 미리보기 모드 (실제 발송 안 함) ===")
        for name, to_addr, projects, tasks, html in reports:
            fname = f"report_{name}.html"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(html)
            addr = to_addr or "(메일주소 미입력)"
            print(f"  {name}: 프로젝트 {len(projects)} / Task {len(tasks)}  → {addr}   [{fname} 저장]")
        print("\n실제 발송하려면:  python send_reports.py --send")
        return

    # 실제 발송
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        print("❌ config.py 의 SMTP_USER / SMTP_PASSWORD 를 먼저 채워주세요.")
        return

    print("SMTP 접속 중...")
    server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)
    try:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        for name, to_addr, projects, tasks, html in reports:
            if not to_addr:
                print(f"  ⏭ {name}: 메일주소 미입력 → 건너뜀")
                continue
            subject = f"[프로젝트 리포트] {name} — 프로젝트 {len(projects)} / Task {len(tasks)}"
            send_mail(server, to_addr, subject, html)
            print(f"  ✅ {name} → {to_addr} 발송 완료")
    finally:
        server.quit()
    print("완료.")


if __name__ == "__main__":
    main()
