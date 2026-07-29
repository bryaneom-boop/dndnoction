"""
'프로젝트 관리_DB' 에서 담당자별(Bryan / Eric / Alex / Michael) 프로젝트를
각각 개별 테이블로 출력한다.

- relation(고객사/공급사) 은 실제 이름으로 풀어서 표시
- 핵심 컬럼만 출력 (버튼/파일/시각 등 잡정보 제외)

실행:  python people_projects.py
"""

import bryan  # _call / print_table 재사용

# 프로젝트 관리_DB
DB_ID = "32b5658a-871f-81f4-9daa-f918d575d389"

# 출력할 사람: 표시이름 -> 담당자 매칭 키워드(소문자, 부분일치)
PEOPLE = [
    ("Bryan", "bryan"),
    ("Eric", "eric"),
    ("Alex", "alex"),
    ("Michael", "michael"),
    ("Calvin", "calvin"),
]

# 출력할 컬럼 (순서 유지). DB 에 있는 속성명과 일치해야 함.
KEEP_COLUMNS = [
    "프로젝트명",
    "상태",
    "담당자",
    "계약형태",
    "고객사",
    "공급사",
    "시작일",
    "마감일",
    "D-day",
    "지연사유",
]

# relation 페이지 제목 캐시 {page_id: title}
_title_cache = {}


def resolve_page_title(page_id):
    """relation 대상 페이지의 제목을 가져온다 (캐시 사용)."""
    if page_id in _title_cache:
        return _title_cache[page_id]
    page = bryan._call(f"https://api.notion.com/v1/pages/{page_id}")
    title = ""
    for v in page.get("properties", {}).values():
        if v.get("type") == "title":
            title = "".join(x["plain_text"] for x in v["title"])
            break
    _title_cache[page_id] = title or "(무제목)"
    return _title_cache[page_id]


def cell_value(v):
    """속성값 -> 문자열. relation 은 실제 제목으로 변환."""
    t = v.get("type")
    if t == "relation":
        titles = [resolve_page_title(rel["id"]) for rel in v["relation"]]
        return ", ".join(titles)
    return bryan.prop_value(v)


def people_names(props):
    """담당자 people 속성의 이름 리스트."""
    for v in props.values():
        if v.get("type") == "people":
            return [p.get("name", "") for p in v["people"]]
    return []


def query_all(db_id):
    rows, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = bryan._call(
            f"https://api.notion.com/v1/databases/{db_id}/query", "POST", body
        )
        rows.extend(res.get("results", []))
        if res.get("has_more"):
            cursor = res.get("next_cursor")
        else:
            break
    return rows


def main():
    all_rows = query_all(DB_ID)

    for display_name, keyword in PEOPLE:
        # 담당자 이름에 keyword 가 들어간 행만
        mine = [
            row
            for row in all_rows
            if any(keyword in n.lower() for n in people_names(row["properties"]))
        ]

        print("\n" + "=" * 70)
        print(f"■ {display_name} 프로젝트  ({len(mine)}개)")
        print("=" * 70)

        if not mine:
            print("  (담당 프로젝트 없음)")
            continue

        table = [
            [cell_value(row["properties"][c]) for c in KEEP_COLUMNS] for row in mine
        ]
        bryan.print_table(KEEP_COLUMNS, table)


if __name__ == "__main__":
    main()
