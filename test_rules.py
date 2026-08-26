"""Qoidalar dvigatelini tekshirish: python test_rules.py

Notion'ga ulanmaydi - haqiqiy bazadan olingan namunalar ustida ishlaydi.
"""

import datetime as dt

from app import rules
from app.notion import Task

TODAY = dt.date(2026, 8, 26)


def make(
    title="",
    status="План",
    start=None,
    deadline=None,
    assignees=(),
    owners=(),
    edited=None,
) -> Task:
    moment = dt.datetime(2026, 8, 20, 10, 0, tzinfo=dt.timezone.utc)
    return Task(
        page_id="test-page-id",
        url="https://notion.so/test",
        title=title,
        status=status,
        start=start,
        deadline=deadline,
        assignees=list(assignees),
        owners=list(owners),
        note="",
        created=moment,
        edited=edited or moment,
        has_subtasks=False,
    )


def codes(task: Task) -> set[str]:
    return {i.code for i in rules.check_task(task, TODAY)}


def check(name: str, condition: bool) -> bool:
    print(f"  {'PASS' if condition else 'FAIL'}  {name}")
    return condition


def main() -> int:
    results = []
    print("\n== Haqiqiy bazadan olingan holatlar ==\n")

    # 1. Nomsiz zadacha (bazada bor)
    print("1) Nomi bo'sh zadacha")
    got = codes(make(title="", assignees=["Ravshan"]))
    results.append(check("no_title topildi", "no_title" in got))

    # 2. Deadline boshlanishdan oldin (bazada bor: Дата 08-26, deadline 08-21)
    print("2) Deadline boshlanish sanasidan oldin")
    got = codes(
        make(
            title="Zamarozka boyicha xar bir tp ga minimal plan qoyish Set va super",
            status="Стрт",
            start=dt.date(2026, 8, 26),
            deadline=dt.date(2026, 8, 21),
            assignees=["Bekzod"],
            owners=["Bekzod"],
        )
    )
    results.append(
        check("deadline_before_start topildi", "deadline_before_start" in got)
    )
    results.append(check("overdue ham topildi", "overdue" in got))

    # 3. Tugallanmagan nom (bazada bor: "... shu")
    print("3) Tugallanmagan nom")
    got = codes(
        make(
            title="agent qizlar bn man mikrafonni beraman …. shu",
            start=dt.date(2026, 9, 1),
            deadline=dt.date(2026, 8, 1),
            assignees=["Ravshan"],
        )
    )
    results.append(check("unfinished topildi", "unfinished" in got))
    results.append(check("vague topildi (shu)", "vague" in got))

    # 4. Ijrochi va deadline yo'q
    print("4) Ijrochi va deadline yo'q")
    got = codes(make(title="Savushkin zavodga Zakaz Prognoz tayyorlash"))
    results.append(check("no_assignee topildi", "no_assignee" in got))
    results.append(check("no_deadline topildi", "no_deadline" in got))
    results.append(check("no_start topildi", "no_start" in got))

    # 5. Juda qisqa nom
    print("5) Juda qisqa nom")
    got = codes(
        make(
            title="shtarflarni qoyish",
            start=dt.date(2026, 8, 26),
            deadline=dt.date(2026, 8, 30),
            assignees=["Ravshan"],
            owners=["Ravshan"],
        )
    )
    results.append(check("title_too_short topildi", "title_too_short" in got))

    # 6. Qotib qolgan (Стрт, 10 kundan beri o'zgarish yo'q)
    print("6) Стрт da qotib qolgan")
    got = codes(
        make(
            title="Sriq bola va Havasga taklif hujjatini tayyorlash",
            status="Стрт",
            start=dt.date(2026, 8, 10),
            deadline=dt.date(2026, 9, 1),
            assignees=["Bekzod"],
            owners=["Bekzod"],
            edited=dt.datetime(2026, 8, 10, tzinfo=dt.timezone.utc),
        )
    )
    results.append(check("stale topildi", "stale" in got))

    # 7. To'g'ri yozilgan zadacha - hech qanday muammo bo'lmasin
    print("7) Qoidaga to'liq mos zadacha")
    good = make(
        title="Savushkin zavodiga sentabr oyi uchun zakaz prognozini tayyorlash",
        status="План",
        start=dt.date(2026, 8, 26),
        deadline=dt.date(2026, 8, 30),
        assignees=["Ravshan"],
        owners=["Farida"],
        edited=dt.datetime(2026, 8, 26, tzinfo=dt.timezone.utc),
    )
    issues = rules.check_task(good, TODAY)
    results.append(check(f"muammo yo'q (topilgan: {[i.code for i in issues]})", not issues))
    results.append(check("ball 100", rules.score(issues) == 100))
    results.append(check("verdikt mos", rules.verdict(issues).startswith("✅")))

    # 8. Ball hisobi
    print("8) Ball va verdikt")
    bad = make(title="", assignees=[])
    bad_issues = rules.check_task(bad, TODAY)
    results.append(check("blocker bor -> ❌", rules.verdict(bad_issues).startswith("❌")))
    results.append(check("ball 100 dan kichik", rules.score(bad_issues) < 100))
    results.append(check("ball manfiy emas", rules.score(bad_issues) >= 0))

    # 9. Takrorlanuvchi kunlik hisobot - qoidalar yumshoq
    print("9) Kunlik takrorlanuvchi zadacha")
    routine = make(
        title="Кунлик РОП 1",
        status="Стрт",
        start=TODAY,
        assignees=["Ravshan"],
        owners=["Farida"],
        edited=dt.datetime(2026, 8, 26, tzinfo=dt.timezone.utc),
    )
    results.append(check("routine deb tanildi", rules.is_routine(routine)))
    got = codes(routine)
    results.append(check("qisqa nom uchun jarima yo'q", "title_too_short" not in got))
    results.append(check("fe'l yo'qligi kechiriladi", "no_action_verb" not in got))
    routine_issues = rules.check_task(routine, TODAY)
    results.append(
        check(
            "deadline yo'qligi blocker emas",
            all(i.severity != rules.BLOCKER for i in routine_issues),
        )
    )
    # Oddiy zadachada esa deadline yo'qligi blocker bo'lib qolsin
    normal = make(
        title="Savushkin zavodiga zakaz prognozini tayyorlash",
        start=TODAY,
        assignees=["Ravshan"],
        owners=["Farida"],
    )
    normal_issues = rules.check_task(normal, TODAY)
    results.append(
        check(
            "oddiy zadachada deadline yo'q -> blocker",
            any(
                i.code == "no_deadline" and i.severity == rules.BLOCKER
                for i in normal_issues
            ),
        )
    )

    # 10. overdue_days hisobi
    print("10) Muddat hisobi")
    t = make(title="test uchun zadacha", deadline=dt.date(2026, 8, 20))
    results.append(check("6 kun o'tgan", rules.overdue_days(t, TODAY) == 6))
    t2 = make(title="test uchun zadacha", deadline=dt.date(2026, 9, 20))
    results.append(check("kelajak -> 0", rules.overdue_days(t2, TODAY) == 0))
    t3 = make(title="test uchun zadacha", start=dt.date(2026, 8, 1))
    results.append(check("deadline yo'q -> Дата ishlatiladi", rules.overdue_days(t3, TODAY) == 25))

    passed = sum(results)
    total = len(results)
    print(f"\n== Natija: {passed}/{total} ==\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
