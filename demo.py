"""Notion tokensiz namoyish: python demo.py

Bazadan olingan haqiqiy 25 ta zadacha ustida qoidalar qanday ishlashini
ko'rsatadi. Bot Telegram'ga aynan shunday hisobot yuboradi.
"""

import datetime as dt
import json

from app import rules
from app.notion import Task

TODAY = dt.date(2026, 8, 26)

# "Durust задача дашборд" bazasidan olingan haqiqiy yozuvlar
SAMPLE = [
    ("mahsulot degustatsiya", "План", "2026-09-01", "2026-09-01", 1, 1),
    ("target uchun durustda ishlash uchun 5ta sabab", "План", "2026-09-01", "2026-09-01", 1, 1),
    ("agent qiz ogil aralsh teretoriyadan ishlash ofisda ishlash oxshagan savollar", "План", "2026-09-01", "2026-09-01", 1, 1),
    ("agent qizlar bn man mikrafonni beraman .... shu", "План", "2026-09-01", "2026-08-01", 1, 1),
    ("stryom norm rahbar bn xodimlar qilgan ish xaqida", "План", "2026-09-01", "2026-09-01", 1, 1),
    ("Кунлик РОП 1", "Стрт", "2026-08-26", None, 1, 0),
    ("Хафталик Бухгалтер Шухрат", "План", "2026-08-26", None, 1, 0),
    ("Kunlik Operator yordamchisi", "Стрт", "2026-08-26", None, 1, 0),
    ("Оператор кунли очет", "Стрт", "2026-08-26", None, 1, 0),
    ("", "План", None, None, 1, 0),
    ("Savushkin zavodga Zakaz (Prognoz)", "План", None, None, 1, 0),
    ("", "План", None, None, 1, 0),
    ("Прогрев кино", "План", "2026-08-25", None, 1, 0),
    ("shtarflarni qoyish", "План", "2026-08-26", "2026-08-25", 1, 0),
    ("Sriq bola va Havasga pridlojeniya tayorlasha", "Стрт", "2026-08-28", "2026-09-01", 1, 0),
    ("поляга чикиш бозорга", "План", "2026-08-26", "2026-08-26", 1, 0),
    ("поляга чикиш олмазорга", "План", "2026-08-27", "2026-08-26", 1, 0),
    ("Zamarozka boyicha xar bir tp ga minimal plan qoyish Set va super", "Стрт", "2026-08-26", "2026-08-21", 1, 1),
    ("zamarozka xamirlarni konkurentini organip tp xodimlarga utp orgatish avgust oyi oxirigacha savdo strategiyasini berish. super va set", "План", "2026-08-26", "2026-08-25", 2, 1),
    ('ООО "FRESH WAVE"', "План", "2026-08-25", "2026-08-25", 1, 0),
]


def build() -> list[Task]:
    tasks = []
    moment = dt.datetime(2026, 8, 20, tzinfo=dt.timezone.utc)
    for title, status, start, deadline, n_assignee, n_owner in SAMPLE:
        tasks.append(
            Task(
                page_id=f"demo-{len(tasks)}",
                url="https://notion.so/demo",
                title=title,
                status=status,
                start=dt.date.fromisoformat(start) if start else None,
                deadline=dt.date.fromisoformat(deadline) if deadline else None,
                assignees=["Xodim"] * n_assignee,
                owners=["Rahbar"] * n_owner,
                note="",
                created=moment,
                edited=moment,
                has_subtasks=False,
            )
        )
    return tasks


def main() -> None:
    tasks = build()
    checked = [(t, rules.check_task(t, TODAY)) for t in tasks]
    bad = [p for p in checked if any(i.severity == rules.BLOCKER for i in p[1])]
    warn = [p for p in checked if p[1] and p not in bad]
    clean = [p for p in checked if not p[1]]
    overdue = [p for p in checked if rules.is_overdue(p[0], TODAY)]

    print(f"\n{'=' * 62}")
    print(f"  KUNLIK TEKSHIRUV - {TODAY}")
    print(f"{'=' * 62}\n")
    print(f"  Jami aktiv zadacha : {len(tasks)}")
    print(f"  Qoidaga mos        : {len(clean)}")
    print(f"  Qisman mos         : {len(warn)}")
    print(f"  Mos emas           : {len(bad)}")
    print(f"  Muddati o'tgan     : {len(overdue)}")

    counter: dict[str, int] = {}
    for _, issues in checked:
        for issue in issues:
            key = issue.message.split(".")[0].split("(")[0].strip()
            counter[key] = counter.get(key, 0) + 1
    print("\n  Eng ko'p uchragan kamchiliklar:")
    for name, count in sorted(counter.items(), key=lambda kv: -kv[1])[:6]:
        print(f"    {count:2d}x  {name}")

    print(f"\n{'-' * 62}")
    print("  ENG MUAMMOLI 5 TA ZADACHA")
    print(f"{'-' * 62}")
    for task, issues in sorted(checked, key=lambda p: rules.score(p[1]))[:5]:
        print(f"\n  {task.short}")
        print(f"  {rules.verdict(issues)}  |  {rules.score(issues)}/100  |  {task.status}")
        for issue in issues:
            mark = "!!" if issue.severity == rules.BLOCKER else " ~"
            print(f"   {mark} {issue.message}")
    print()


if __name__ == "__main__":
    main()
