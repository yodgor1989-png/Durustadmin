"""Sozlamalar: barcha maxfiy kalitlar .env faylidan o'qiladi."""

import os

from dotenv import load_dotenv

load_dotenv()


# Majburiy sozlamalar import paytida emas, validate() chaqirilganda
# tekshiriladi - shunda testlar .env'siz ham ishlaydi.
_REQUIRED: list[str] = []


def _req(name: str) -> str:
    _REQUIRED.append(name)
    return os.getenv(name, "").strip()


def validate() -> None:
    """Majburiy sozlamalar to'ldirilganini tekshiradi."""
    missing = [name for name in _REQUIRED if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError(
            ".env faylida quyidagilar to'ldirilmagan: "
            + ", ".join(missing)
            + ". .env.example ga qarang."
        )


# --- Telegram ---------------------------------------------------------------
BOT_TOKEN = _req("BOT_TOKEN")
# Kunlik hisobot yuboriladigan guruh (masalan -1002561638240)
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0") or 0)
# Faqat shu ID'lar Notion'ni o'zgartira oladi. Bo'sh bo'lsa - guruhdagi hamma.
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}

# --- Notion -----------------------------------------------------------------
NOTION_TOKEN = _req("NOTION_TOKEN")
# Baza ID'si .env dan olinadi - kod ochiq repozitoriyada yotgani uchun
# ish ma'lumotlari sozlamalarda qolsin.
NOTION_DATABASE_ID = _req("NOTION_DATABASE_ID").replace("-", "")
NOTION_VERSION = "2022-06-28"

# --- OpenAI -----------------------------------------------------------------
OPENAI_API_KEY = _req("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")

# --- Notion ustunlari (bazadagi aniq nomlar) --------------------------------
P_TITLE = "Вазифа"
P_STATUS = "Статус"
P_DATE = "Дата"
P_DEADLINE = "Дедлайн (настройка)"
P_DONE_DATE = "Дата завершение"
P_ASSIGNEE = "Исполнитель"
P_OWNER = "Ответственный"
P_WATCHER = "Наблюдатель"
P_NOTE = "Заметка"
P_SUBTASK = "Подзадача"

# Statuslar
STATUS_TODO = "План"
STATUS_STARTED = "Стрт"
STATUS_AUDIT = "Аудт"
STATUS_DONE = "Выпл"
STATUS_REJECTED = "Откз"
ACTIVE_STATUSES = [STATUS_TODO, STATUS_STARTED, STATUS_AUDIT]

# --- Qoida chegaralari ------------------------------------------------------
# Nom kamida shuncha so'zdan iborat bo'lishi kerak
MIN_TITLE_WORDS = int(os.getenv("MIN_TITLE_WORDS", "3"))
# "Стрт" statusida shuncha kundan ko'p turib qolsa - qotib qolgan
STALE_DAYS = int(os.getenv("STALE_DAYS", "7"))
# Kunlik hisobot vaqti (Asia/Tashkent)
REPORT_HOUR = int(os.getenv("REPORT_HOUR", "9"))
REPORT_MINUTE = int(os.getenv("REPORT_MINUTE", "0"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tashkent")

# Notion sahifasiga ham komentariya yozilsinmi
WRITE_TO_NOTION = os.getenv("WRITE_TO_NOTION", "true").lower() == "true"
