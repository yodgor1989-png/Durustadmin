"""Ulanishlarni tekshirish: python check.py

Botni ishga tushirishdan oldin uchta ulanishni sinaydi:
Telegram, Notion, OpenAI.
"""

import asyncio
import datetime as dt

import httpx

from app import config


def line(ok: bool | None, label: str, detail: str = "") -> None:
    mark = {True: "[OK]  ", False: "[XATO]", None: "[?]   "}[ok]
    print(f"{mark} {label}" + (f" - {detail}" if detail else ""))


async def check_telegram() -> bool:
    if not config.BOT_TOKEN:
        line(False, "Telegram", "BOT_TOKEN .env da yo'q")
        return False
    async with httpx.AsyncClient(timeout=20) as http:
        try:
            resp = await http.get(
                f"https://api.telegram.org/bot{config.BOT_TOKEN}/getMe"
            )
            data = resp.json()
        except Exception as exc:
            line(False, "Telegram", str(exc)[:120])
            return False
    if not data.get("ok"):
        line(False, "Telegram", str(data.get("description"))[:120])
        return False
    bot = data["result"]
    line(True, "Telegram", f"@{bot['username']} (id {bot['id']})")
    if not bot.get("can_read_all_group_messages"):
        line(
            None,
            "Telegram privacy",
            "guruhda faqat buyruq va reply'larni ko'radi "
            "(BotFather -> /setprivacy -> Disable qilsangiz hammasini ko'radi)",
        )
    return True


async def check_notion() -> bool:
    if not config.NOTION_TOKEN:
        line(False, "Notion", "NOTION_TOKEN .env da to'ldirilmagan")
        return False
    from app.notion import NotionClient

    client = NotionClient()
    try:
        users = await client.load_users()
        line(True, "Notion auth", f"{len(users)} ta foydalanuvchi ko'rinyapti")

        database_id = await client.resolve_database_id()
        if database_id != config.NOTION_DATABASE_ID:
            line(
                None,
                "Notion baza ID",
                f"sozlamadagi ID ishlamadi, topilgani: {database_id}\n"
                f"      .env da NOTION_DATABASE_ID={database_id} qilib "
                f"qo'ysangiz tezroq ishga tushadi",
            )
        else:
            line(True, "Notion baza ID", database_id)

        tasks = await client.fetch_active_tasks()
        line(True, "Notion baza", f"{len(tasks)} ta aktiv zadacha o'qildi")

        from app import rules

        today = dt.date.today()
        bad = sum(
            1
            for t in tasks
            if any(i.severity == rules.BLOCKER for i in rules.check_task(t, today))
        )
        overdue = sum(1 for t in tasks if rules.is_overdue(t, today))
        line(None, "Tahlil", f"qoidaga mos emas: {bad}, muddati o'tgan: {overdue}")
        return True
    except Exception as exc:
        line(False, "Notion", str(exc)[:200])
        print(
            "\n      Maslahat: integratsiya 'Management' sahifasiga ulanganmi?\n"
            "      Notion -> sahifa -> ... -> Connections -> integratsiyani qo'shing.\n"
        )
        return False
    finally:
        await client.close()


async def check_openai() -> bool:
    if not config.OPENAI_API_KEY:
        line(False, "OpenAI", "OPENAI_API_KEY .env da yo'q")
        return False
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    try:
        page = await client.models.list()
        models = sorted(model.id for model in page.data)
        line(True, "OpenAI auth", f"mavjud modellar: {', '.join(models) or 'yo`q'}")
    except Exception as exc:
        line(False, "OpenAI auth", str(exc)[:160])
        return False

    if config.OPENAI_MODEL not in models:
        line(
            False,
            "OpenAI model",
            f"'{config.OPENAI_MODEL}' ochilmagan. .env da OPENAI_MODEL ni "
            f"yuqoridagilardan biriga o'zgartiring.",
        )
        return False

    from app import ai

    try:
        answer = await ai._chat("Qisqa javob ber.", "Faqat 'ishladi' deb yoz.")
        line(True, "OpenAI javob", answer[:60])
        return True
    except Exception as exc:
        detail = str(exc)[:160]
        line(False, "OpenAI javob", detail)
        if "credit" in detail.lower() or "quota" in detail.lower():
            print(
                "\n      Hisobda kredit yo'q. platform.openai.com/settings/"
                "organization/billing dan to'ldiring.\n"
                "      Kredit qo'shilmaguncha bot AI'siz ishlaydi: qoidalar "
                "tekshiriladi, lekin komentariya quruq ro'yxat bo'ladi.\n"
            )
        return False


async def main() -> None:
    print("\n=== Durust task-bot: ulanishlarni tekshirish ===\n")
    results = [
        await check_telegram(),
        await check_notion(),
        await check_openai(),
    ]
    print()
    if all(results):
        print("Hammasi tayyor. Botni ishga tushiring:  python main.py\n")
    else:
        print("Yuqoridagi xatolarni tuzating, so'ng qayta ishga tushiring.\n")


if __name__ == "__main__":
    asyncio.run(main())
