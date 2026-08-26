"""Zadacha qoidalari: deterministik (AI'siz) tekshiruvlar.

Har bir tekshiruv `Issue` qaytaradi. AI keyin shu ro'yxat ustiga
odamga tushunarli komentariya yozadi.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from app import config
from app.notion import Task

# Og'irlik darajalari
BLOCKER = "blocker"  # zadacha shu holida ishga yaroqsiz
WARNING = "warning"  # ishlash mumkin, lekin qoidaga to'liq mos emas


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    message: str

    @property
    def icon(self) -> str:
        return "🔴" if self.severity == BLOCKER else "🟡"


# Natijani o'lchab bo'lmaydigan, "suv" so'zlar
VAGUE_WORDS = {
    "shu", "shunga", "oxshagan", "va hokazo", "vahokazo", "hokazo",
    "narsa", "nimadir", "bir narsa", "koramiz", "ko'ramiz", "qaraymiz",
    "ishlash", "qilish", "gaplashish", "urganish", "o'rganish",
    "norm", "stryom", "yaxshilash", "tekshirish",
}

# Tugallanmagan fikr belgilari
UNFINISHED = ("...", "…", "..", "??", "--")

# Aniq harakat fe'llari (o'zbek + rus) - konkretlik belgisi
ACTION_VERBS = (
    "tayyorla", "yubor", "yoz", "qo'y", "qoy", "tuz", "hisobla", "kelish",
    "imzola", "sotib ol", "yetkaz", "chiqar", "o'tkaz", "otkaz", "to'la", "tola",
    "topshir", "nazorat", "taqdim", "kelishtir", "shakllantir", "tasdiqla",
    "подготов", "отправ", "написа", "постав", "состав", "рассчит", "заключ",
    "подпис", "куп", "провед", "оплат", "сдать", "утверд", "предостав",
)


# Takrorlanuvchi (kunlik/haftalik/oylik) hisobot zadachalari.
# Bular shablon bo'lgani uchun nom qoidalari ularga yumshoqroq qo'llanadi.
ROUTINE_MARKERS = (
    "кунлик", "kunlik", "хафталик", "haftalik", "ҳафталик",
    "ойлик", "oylik", "очет", "отчет", "отчёт", "hisobot",
    "ежедневн", "еженедельн", "kundalik",
)


def _words(text: str) -> list[str]:
    return [w for w in re.split(r"[\s,.;:!?()\[\]/\\-]+", text.lower()) if w]


def is_routine(task: Task) -> bool:
    """Kunlik/haftalik takrorlanuvchi hisobot zadachasimi."""
    low = task.title.lower()
    return any(marker in low for marker in ROUTINE_MARKERS)


def check_task(task: Task, today: dt.date) -> list[Issue]:
    """Bitta zadachani barcha qoidalar bo'yicha tekshiradi."""
    issues: list[Issue] = []
    title = task.title.strip()
    words = _words(title)
    routine = is_routine(task)

    # 1. Nom bor va bo'sh emas
    if not title:
        issues.append(
            Issue("no_title", BLOCKER, "Zadachaning nomi umuman yozilmagan.")
        )
    else:
        # 2. Nom yetarlicha batafsil
        # Takrorlanuvchi hisobotlarga bu qoida qo'llanmaydi - ular shablon.
        if not routine and len(words) < config.MIN_TITLE_WORDS:
            issues.append(
                Issue(
                    "title_too_short",
                    BLOCKER,
                    f"Nom juda qisqa ({len(words)} so'z). "
                    f"Kamida {config.MIN_TITLE_WORDS} so'z bo'lsin: "
                    f"nima qilinadi + nima ustida + qanday natija.",
                )
            )

        # 3. Tugallanmagan fikr
        if any(mark in title for mark in UNFINISHED):
            issues.append(
                Issue(
                    "unfinished",
                    BLOCKER,
                    "Nom tugallanmagan (\"...\" bilan tugagan). "
                    "Fikr oxirigacha yozilishi kerak.",
                )
            )

        # 4. Noaniq, o'lchab bo'lmaydigan ifodalar
        vague = [w for w in words if w in VAGUE_WORDS]
        if vague:
            issues.append(
                Issue(
                    "vague",
                    WARNING,
                    f"Noaniq so'zlar ishlatilgan: {', '.join(sorted(set(vague)))}. "
                    f"Natijani o'lchab bo'ladigan qilib yozing.",
                )
            )

        # 5. Aniq harakat fe'li bormi (takrorlanuvchi hisobotlardan tashqari)
        low = title.lower()
        if not routine and not any(verb in low for verb in ACTION_VERBS):
            issues.append(
                Issue(
                    "no_action_verb",
                    WARNING,
                    "Nomda aniq harakat yo'q. "
                    "\"Nima qilish kerak?\" degan savolga javob bo'lsin "
                    "(masalan: tayyorlash, yuborish, kelishish, topshirish).",
                )
            )

    # 6. Ijrochi belgilangan
    if not task.assignees:
        issues.append(
            Issue("no_assignee", BLOCKER, "Ijrochi (Исполнитель) belgilanmagan.")
        )

    # 7. Mas'ul belgilangan
    if not task.owners:
        issues.append(
            Issue(
                "no_owner",
                WARNING,
                "Mas'ul (Ответственный) belgilanmagan - "
                "natijani kim qabul qiladi noma'lum.",
            )
        )

    # 8. Boshlanish sanasi
    if task.start is None:
        issues.append(
            Issue("no_start", WARNING, "Boshlanish sanasi (Дата) qo'yilmagan.")
        )

    # 9. Deadline. Kunlik hisobotlarda "Дата" ning o'zi muddat vazifasini
    # bajaradi, shuning uchun ular uchun bu faqat ogohlantirish.
    if task.deadline is None:
        issues.append(
            Issue(
                "no_deadline",
                WARNING if routine else BLOCKER,
                "Deadline (Дедлайн) qo'yilmagan - qachon tugashi noma'lum.",
            )
        )

    # 10. Deadline mantiqiy: boshlanishdan oldin bo'lmasin
    if task.start and task.deadline and task.deadline < task.start:
        issues.append(
            Issue(
                "deadline_before_start",
                BLOCKER,
                f"Deadline ({task.deadline}) boshlanish sanasidan "
                f"({task.start}) oldin. Sanalar chalkash.",
            )
        )

    # 11. Muddati o'tgan, lekin hali yopilmagan
    days = overdue_days(task, today)
    if days > 0:
        issues.append(
            Issue(
                "overdue",
                BLOCKER,
                f"Muddati {days} kun oldin o'tgan, status hali \"{task.status}\".",
            )
        )

    # 12. "Стрт" da uzoq qotib qolgan
    if task.status == config.STATUS_STARTED:
        idle = (today - task.edited.date()).days
        if idle >= config.STALE_DAYS:
            issues.append(
                Issue(
                    "stale",
                    WARNING,
                    f"{idle} kundan beri hech qanday o'zgarish yo'q, "
                    f"lekin status \"boshlangan\".",
                )
            )

    return issues


def overdue_days(task: Task, today: dt.date) -> int:
    """Muddati necha kun o'tgan (o'tmagan bo'lsa 0)."""
    deadline = task.effective_deadline
    if deadline is None:
        return 0
    delta = (today - deadline).days
    return delta if delta > 0 else 0


def is_overdue(task: Task, today: dt.date) -> bool:
    return overdue_days(task, today) > 0


def score(issues: list[Issue]) -> int:
    """0-100 ball. Blocker -20, warning -7."""
    total = 100
    for issue in issues:
        total -= 20 if issue.severity == BLOCKER else 7
    return max(total, 0)


def verdict(issues: list[Issue]) -> str:
    if any(i.severity == BLOCKER for i in issues):
        return "❌ Qoidaga mos emas"
    if issues:
        return "⚠️ Qisman mos"
    return "✅ Qoidaga mos"
