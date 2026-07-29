"""
Notion 에서 'bryan' 페이지 정보를 찾아 테이블 형식으로 출력하는 스크립트.

사용 전 준비:
  1) config.py 의 NOTION_TOKEN 설정 (또는 환경변수 NOTION_TOKEN)
  2) 'bryan' 페이지를 Notion 에서 Integration 에 연결(Connections)

실행:  python bryan.py
"""

import json
import os
import sys
import urllib.request
import urllib.error
import unicodedata

import config

# Windows 콘솔 한글 깨짐 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

TOKEN = os.environ.get("NOTION_TOKEN", config.NOTION_TOKEN)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": config.NOTION_VERSION,
    "Content-Type": "application/json",
}

SEARCH_KEYWORD = "bryan"


# ----------------------------------------------------------------------
# Notion API 호출
# ----------------------------------------------------------------------
def _call(url, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        return json.load(e)  # 에러도 JSON 으로 반환 (code / message 확인용)


def search(keyword):
    """제목에 keyword 가 들어간 페이지/DB 검색."""
    body = {"query": keyword}
    return _call("https://api.notion.com/v1/search", "POST", body).get("results", [])


# ----------------------------------------------------------------------
# 값 추출 헬퍼
# ----------------------------------------------------------------------
def prop_value(v):
    """Notion 속성 하나를 사람이 읽을 수 있는 문자열로 변환."""
    t = v.get("type")
    if t == "title":
        return "".join(x["plain_text"] for x in v["title"])
    if t == "rich_text":
        return "".join(x["plain_text"] for x in v["rich_text"])
    if t == "select":
        return v["select"]["name"] if v["select"] else ""
    if t == "multi_select":
        return ", ".join(o["name"] for o in v["multi_select"])
    if t == "status":
        return v["status"]["name"] if v["status"] else ""
    if t == "date":
        if not v["date"]:
            return ""
        d = v["date"]
        return d["start"] + (f" ~ {d['end']}" if d.get("end") else "")
    if t == "people":
        return ", ".join(p.get("name", "?") for p in v["people"])
    if t == "checkbox":
        return "✔" if v["checkbox"] else "✘"
    if t in ("number", "url", "email", "phone_number"):
        return "" if v[t] is None else str(v[t])
    if t == "formula":
        f = v["formula"]
        return "" if f.get(f["type"]) is None else str(f[f["type"]])
    return f"({t})"


def page_title(r):
    """검색 결과 항목의 제목."""
    if r["object"] == "database":
        return "".join(x["plain_text"] for x in r.get("title", [])) or "(무제목)"
    for v in r.get("properties", {}).values():
        if v.get("type") == "title" and v["title"]:
            return v["title"][0]["plain_text"]
    return "(무제목)"


def get_page_blocks(block_id, depth=0):
    """블록과 그 자식 블록을 재귀적으로 (타입, 텍스트, 깊이) 리스트로 반환."""
    lines = []
    cursor = None
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        res = _call(url)
        for b in res.get("results", []):
            bt = b["type"]
            content = b.get(bt, {})
            rich = content.get("rich_text", []) if isinstance(content, dict) else []
            text = "".join(x["plain_text"] for x in rich)
            # to_do 는 체크 상태 표시
            if bt == "to_do":
                mark = "[x]" if content.get("checked") else "[ ]"
                text = f"{mark} {text}"
            if text:
                lines.append((bt, text, depth))
            # 자식 블록 재귀
            if b.get("has_children"):
                lines.extend(get_page_blocks(b["id"], depth + 1))
        if res.get("has_more"):
            cursor = res.get("next_cursor")
        else:
            break
    return lines


# ----------------------------------------------------------------------
# 테이블 출력 (한글/전각 정렬 지원)
# ----------------------------------------------------------------------
def _width(s):
    """전각 문자를 2칸으로 계산한 표시 폭."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))


def _pad(s, width):
    return str(s) + " " * (width - _width(s))


def print_table(headers, rows):
    """headers(리스트) 와 rows(리스트의 리스트)를 정렬된 표로 출력."""
    cols = list(zip(*([headers] + rows))) if rows else [[h] for h in headers]
    widths = [max(_width(cell) for cell in col) for col in cols]

    def line(cells):
        return "| " + " | ".join(_pad(c, w) for c, w in zip(cells, widths)) + " |"

    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    print(sep)
    print(line(headers))
    print(sep)
    for row in rows:
        print(line(row))
    print(sep)


# ----------------------------------------------------------------------
# 메인
# ----------------------------------------------------------------------
def main():
    results = search(SEARCH_KEYWORD)
    if not results:
        print(f"'{SEARCH_KEYWORD}' 에 해당하는 페이지를 찾지 못했습니다.")
        print("→ 토큰이 맞는지, 페이지가 Integration 에 연결(Connections)되어 있는지 확인하세요.")
        return

    for r in results:
        obj = r["object"]
        title = page_title(r)
        print(f"\n■ [{obj}] {title}  (id={r['id']})")

        if obj == "page":
            # 속성 테이블
            props = r.get("properties", {})
            if props:
                rows = [[name, prop_value(v)] for name, v in props.items()]
                print_table(["속성", "값"], rows)

            # 본문 블록 테이블
            blocks = get_page_blocks(r["id"])
            if blocks:
                print("\n  · 본문")
                print_table(
                    ["타입", "내용"],
                    [[bt, "  " * depth + text] for bt, text, depth in blocks],
                )

        elif obj == "database":
            res = _call(
                f"https://api.notion.com/v1/databases/{r['id']}/query", "POST", {}
            )
            db_rows = res.get("results", [])
            if not db_rows:
                print("  (행 없음)")
                continue
            headers = list(db_rows[0].get("properties", {}).keys())
            table = [
                [prop_value(row["properties"][h]) for h in headers] for row in db_rows
            ]
            print_table(headers, table)


if __name__ == "__main__":
    main()
