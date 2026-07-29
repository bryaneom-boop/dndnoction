"""
담당자별(Bryan / Eric / Alex / Michael) '프로젝트 & Task' 를 함께 출력한다.

- 프로젝트 관리_DB → 사람별 프로젝트 표
- Task_DB        → 사람별 Task 표 (소속 프로젝트명까지 표시)
- relation(고객사/공급사/소속 프로젝트) 은 실제 이름으로 변환

실행:  python people_pt.py
"""

import bryan
import people_projects as pp  # resolve_page_title / cell_value / query_all / people_names 재사용

PROJECT_DB = "32b5658a-871f-81f4-9daa-f918d575d389"
TASK_DB = "32b5658a-871f-814f-824a-ceafe15f89dc"

PEOPLE = [
    ("Bryan", "bryan"),
    ("Eric", "eric"),
    ("Alex", "alex"),
    ("Michael", "michael"),
    ("Calvin", "calvin"),
]

# 프로젝트 표 컬럼
PROJECT_COLUMNS = [
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

# Task 표 컬럼 (project_DB 는 소속 프로젝트명으로 표시)
TASK_COLUMNS = [
    "작업명",
    "상태",
    "담당자",
    "마감일",
    "project_DB",
    "지연 사유",
]
TASK_HEADERS = ["작업명", "상태", "담당자", "마감일", "소속 프로젝트", "지연사유"]


def filter_by_person(rows, keyword):
    return [
        r
        for r in rows
        if any(keyword in n.lower() for n in pp.people_names(r["properties"]))
    ]


def print_rows(rows, columns, headers):
    table = [[pp.cell_value(r["properties"][c]) for c in columns] for r in rows]
    bryan.print_table(headers, table)


def main():
    projects = pp.query_all(PROJECT_DB)
    tasks = pp.query_all(TASK_DB)

    for display_name, keyword in PEOPLE:
        my_projects = filter_by_person(projects, keyword)
        my_tasks = filter_by_person(tasks, keyword)

        print("\n" + "#" * 72)
        print(f"# {display_name}  —  프로젝트 {len(my_projects)}개 / Task {len(my_tasks)}개")
        print("#" * 72)

        print(f"\n[프로젝트] ({len(my_projects)})")
        if my_projects:
            print_rows(my_projects, PROJECT_COLUMNS, PROJECT_COLUMNS)
        else:
            print("  (없음)")

        print(f"\n[Task] ({len(my_tasks)})")
        if my_tasks:
            print_rows(my_tasks, TASK_COLUMNS, TASK_HEADERS)
        else:
            print("  (없음)")


if __name__ == "__main__":
    main()
