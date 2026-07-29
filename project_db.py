"""
Notion '프로젝트 관리_DB' 의 행들을 테이블로 출력하는 스크립트.

실행:  python project_db.py
"""

import bryan  # _call / prop_value / print_table 재사용

# 프로젝트 관리_DB
DB_ID = "32b5658a-871f-81f4-9daa-f918d575d389"


def query_all(db_id):
    """DB 의 모든 행을 페이지네이션 처리해서 반환."""
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
    rows = query_all(DB_ID)
    if not rows:
        print("행이 없습니다. (DB 연결/권한 확인)")
        return

    # 컬럼 순서: 첫 행의 속성 순서 유지
    headers = list(rows[0].get("properties", {}).keys())
    table = [
        [bryan.prop_value(row["properties"][h]) for h in headers] for row in rows
    ]

    print(f"■ 프로젝트 관리_DB  (행 {len(rows)}개)")
    bryan.print_table(headers, table)


if __name__ == "__main__":
    main()
