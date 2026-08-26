"""OpenAI qatlami: komentariya yozish va zadachani aniqlashtirish."""

from __future__ import annotations

import datetime as dt
import json
import logging

from openai import AsyncOpenAI

from app import config
from app.notion import Task
from app.rules import Issue

logger = logging.getLogger("ai")

# Kalit bo'lmasa ham modul import bo'lishi kerak - bot AI'siz ishlayveradi.
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY) if config.ai_ready() else None

SYSTEM = """Sen "Durust" kompaniyasining task-menejerisiz. Notion'dagi
zadachalarni tekshirasan va rahbar tilida qisqa, konkret fikr bildirasan.

Zadacha qoidalari (SMART):
1. Nom aniq harakatni bildiradi: nima qilinadi + nima ustida + qanday natija.
2. Natija o'lchanadigan bo'lsin (raqam, hujjat, ro'yxat, summa, foiz).
3. Ijrochi va mas'ul belgilangan bo'lsin.
4. Boshlanish sanasi va deadline bo'lsin, deadline boshlanishdan keyin bo'lsin.
5. "shu", "...", "o'xshagan", "norm" kabi noaniq gaplar bo'lmasin.
6. Bitta zadacha - bitta natija. Ko'p ish bo'lsa, bo'lib tashlansin.

Javob qoidalari:
- O'zbek tilida (lotin), sodda va qisqa yoz.
- Maksimum 3-4 gap. Suv quyma, maslahat berma, faqat aniq kamchilikni ayt.
- Ayblama, "qanday bo'lsa to'g'ri" bo'lishini ko'rsat.
"""


# Modellar qo'llab-quvvatlaydigan parametrlar har xil (gpt-4 oilasi
# `max_tokens`, gpt-5 oilasi `max_completion_tokens` va temperature'ni
# qabul qilmaydi). Birinchi chaqiruvda mos variantni topib, eslab qolamiz.
_supported: dict | None = None


def _variants() -> list[dict]:
    return [
        {"temperature": 0.3, "max_tokens": 900},
        {"max_completion_tokens": 900},
        {},
    ]


async def _call(user: str, system: str, extra: dict, json_mode: bool) -> str:
    if client is None:
        raise RuntimeError("OPENAI_API_KEY kiritilmagan")
    kwargs = dict(extra)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = await client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **kwargs,
    )
    return (resp.choices[0].message.content or "").strip()


async def _chat(system: str, user: str, json_mode: bool = False) -> str:
    """Modelga so'rov yuboradi, qo'llab-quvvatlanmagan parametrlarni tashlab."""
    global _supported

    if _supported is not None:
        return await _call(user, system, _supported, json_mode)

    last: Exception | None = None
    for extra in _variants():
        try:
            result = await _call(user, system, extra, json_mode)
        except Exception as exc:
            message = str(exc).lower()
            # Faqat parametr xatosida keyingi variantga o'tamiz.
            if "unsupported" in message or "unrecognized" in message or (
                "param" in message and "not supported" in message
            ):
                last = exc
                logger.info("Model %s bu parametrlarni qabul qilmadi: %s",
                            config.OPENAI_MODEL, list(extra))
                continue
            raise
        _supported = extra
        logger.info("Model %s uchun parametrlar: %s",
                    config.OPENAI_MODEL, extra or "standart")
        return result

    raise last or RuntimeError("Model chaqirilmadi")


def _parse_json(text: str) -> dict:
    """JSON javobni ajratib oladi (```json ... ``` bo'lsa ham)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def task_brief(task: Task) -> str:
    """Zadachani AI uchun matn ko'rinishida beradi."""
    empty = "(bo'sh)"
    assignees = ", ".join(task.assignees) or empty
    owners = ", ".join(task.owners) or empty
    return "\n".join(
        [
            f"Nomi: {task.title or empty}",
            f"Status: {task.status or empty}",
            f"Boshlanish: {task.start or empty}",
            f"Deadline: {task.deadline or empty}",
            f"Ijrochi: {assignees}",
            f"Mas'ul: {owners}",
            f"Izoh: {task.note or empty}",
        ]
    )


async def review(task: Task, issues: list[Issue]) -> str:
    """Zadacha bo'yicha qisqa komentariya."""
    if not issues:
        return "Zadacha qoidaga mos: natija aniq, ijrochi va muddat belgilangan."
    found = "\n".join(f"- {i.message}" for i in issues)
    user = (
        f"Zadacha:\n{task_brief(task)}\n"
        f"Avtomatik tekshiruv topgan kamchiliklar:\n{found}\n\n"
        f"Shu kamchiliklarni 3-4 gapda umumlashtirib, ijrochiga tushunarli "
        f"qilib ayt. Eng muhimini birinchi qo'y."
    )
    try:
        return await _chat(SYSTEM, user)
    except Exception as exc:  # AI ishlamasa ham bot to'xtamasin
        logger.error("AI review xato: %s", exc)
        return found


async def ask_stale(task: Task, days: int) -> str:
    """Muddati o'tgan zadacha uchun izoh so'rash matni."""
    user = (
        f"Zadacha:\n{task_brief(task)}\n"
        f"Bu zadachaning muddati {days} kun oldin o'tgan, ammo hali yopilmagan.\n\n"
        f"Ijrochidan hisobot so'ra. 2-3 gap. Aniq savol ber: nima qilindi, "
        f"nima to'sqinlik qildi, yangi muddat qachon. Do'q urma."
    )
    try:
        return await _chat(SYSTEM, user)
    except Exception as exc:
        logger.error("AI ask_stale xato: %s", exc)
        return (
            f"Bu zadachaning muddati {days} kun oldin o'tgan. "
            f"Iltimos yozing: nima bajarildi, nima to'sqinlik qildi, "
            f"yangi muddat qachon?"
        )


CLARIFY_SYSTEM = SYSTEM + """

Endi sen noaniq gapdan konkret zadacha yasaysan.
Javobni FAQAT JSON qaytar, quyidagi kalitlar bilan:
{
  "ok": true/false,
  "savollar": ["...", "..."],
  "nom": "konkret zadacha nomi",
  "natija": "qanday natija kutiladi (o'lchanadigan)",
  "qadamlar": ["1-qadam", "2-qadam"],
  "deadline_kun": 3
}
Agar zadachani konkret qilish uchun ma'lumot yetmasa: "ok": false qo'y va
"savollar" ga 2-3 ta aniqlovchi savol yoz (nom, natija, qadamlarni bo'sh qoldir).
Agar yetarli bo'lsa: "ok": true, "savollar": [].
"nom" 5-12 so'z, harakat fe'li bilan. "deadline_kun" - bugundan necha kun.
"""


async def clarify(raw_text: str, today: dt.date) -> dict:
    """Erkin matndan konkret zadacha tuzadi yoki savol beradi."""
    user = (
        f"Bugungi sana: {today.isoformat()}\n"
        f"Rahbar shunday dedi: \"{raw_text}\"\n\n"
        f"Shundan konkret zadacha yasa."
    )
    try:
        text = await _chat(CLARIFY_SYSTEM, user, json_mode=True)
        data = _parse_json(text)
    except Exception as exc:
        logger.error("AI clarify xato: %s", exc)
        return {
            "ok": False,
            "savollar": ["AI javob bermadi. Zadachani o'zingiz yozib ko'ring."],
        }
    data.setdefault("ok", False)
    data.setdefault("savollar", [])
    data.setdefault("nom", "")
    data.setdefault("natija", "")
    data.setdefault("qadamlar", [])
    data.setdefault("deadline_kun", 3)
    return data


IMPROVE_SYSTEM = SYSTEM + """

Endi sen mavjud zadachani qayta yozasan.
Javobni FAQAT JSON qaytar:
{
  "nom": "yaxshilangan nom",
  "natija": "kutilayotgan aniq natija",
  "izoh": "nima o'zgardi va nega (1-2 gap)"
}
Nomni 5-12 so'zga sig'dir, harakat fe'li bilan boshla, natijani o'lchanadigan qil.
Asl mazmunni o'zgartirma - faqat aniqlashtir.
"""


async def improve(task: Task) -> dict:
    """Mavjud zadacha nomini konkretlashtiradi."""
    user = f"Zadacha:\n{task_brief(task)}\n\nShuni qoidaga moslab qayta yoz."
    try:
        text = await _chat(IMPROVE_SYSTEM, user, json_mode=True)
        data = _parse_json(text)
    except Exception as exc:
        logger.error("AI improve xato: %s", exc)
        return {"nom": "", "natija": "", "izoh": "AI javob bermadi."}
    data.setdefault("nom", "")
    data.setdefault("natija", "")
    data.setdefault("izoh", "")
    return data
