"""Durust task-menejer boti (aiogram 3)."""

from __future__ import annotations

import asyncio
import datetime as dt
import html
import logging
import secrets
import zoneinfo

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app import ai, config, rules, storage
from app.notion import NotionClient, Task

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("durust-bot")

TZ = zoneinfo.ZoneInfo(config.TIMEZONE)

bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
notion = NotionClient()

# Vaqtinchalik holat (xotirada)
# token -> taklif qilingan yangi nom (tasdiqlash uchun)
proposals: dict[str, dict] = {}
# user_id -> page_id (foydalanuvchi izoh yozishini kutyapmiz)
awaiting_comment: dict[int, str] = {}
# user_id -> oxirgi aniqlashtirish natijasi
draft_tasks: dict[int, dict] = {}


def today() -> dt.date:
    return dt.datetime.now(TZ).date()


def esc(text: str) -> str:
    return html.escape(text or "")


def is_admin(user_id: int) -> bool:
    return not config.ADMIN_IDS or user_id in config.ADMIN_IDS


def short_id(page_id: str) -> str:
    return page_id.replace("-", "")


NOTION_MISSING = (
    "⚙️ <b>Notion hali ulanmagan.</b>\n\n"
    "Bu buyruq Notion bazasini o'qiydi, shuning uchun ishlamaydi.\n\n"
    "Ulash uchun:\n"
    "1. notion.so/my-integrations → New integration\n"
    "2. Secret'ni nusxalang\n"
    "3. Notion'da baza sahifasi → <code>...</code> → Connections → "
    "integratsiyani qo'shing\n"
    "4. Kompyuterda: <code>python notion_token.py</code>\n\n"
    "Shundan keyin botni qayta ishga tushiring."
)


AI_MISSING = "\n".join(
    [
        "⚙️ <b>AI hali ulanmagan.</b>",
        "",
        "Zadacha yasash uchun OpenAI kaliti kerak.",
        ".env da <code>OPENAI_API_KEY</code> ni to'ldiring va hisobda kredit",
        "borligiga ishonch hosil qiling, so'ng botni qayta ishga tushiring.",
        "",
        "<i>Qoidalar tekshiruvi (/tekshir, /eskirgan) AI'siz ham ishlaydi.</i>",
    ]
)


async def ai_guard(message: Message) -> bool:
    """AI ulanmagan bo'lsa tushuntirib, False qaytaradi."""
    if config.ai_ready():
        return True
    await message.answer(AI_MISSING)
    return False


async def notion_guard(message: Message) -> bool:
    """Notion ulanmagan bo'lsa tushuntirib, False qaytaradi."""
    if config.notion_ready():
        return True
    await message.answer(NOTION_MISSING)
    return False


# --- Klaviaturalar ----------------------------------------------------------
def task_keyboard(task: Task, overdue: bool = False) -> InlineKeyboardMarkup:
    sid = short_id(task.page_id)
    rows = [
        [
            InlineKeyboardButton(text="🔍 Tahlil", callback_data=f"rev:{sid}"),
            InlineKeyboardButton(text="✍️ Aniqlashtirish", callback_data=f"imp:{sid}"),
        ],
        [
            InlineKeyboardButton(text="💬 Izoh yozish", callback_data=f"com:{sid}"),
            InlineKeyboardButton(text="🔗 Notion", url=task.url or "https://notion.so"),
        ],
    ]
    if overdue:
        rows.insert(
            1,
            [
                InlineKeyboardButton(
                    text="📩 Izoh so'rash (Notion'ga)", callback_data=f"ask:{sid}"
                )
            ],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Saqlash", callback_data=f"ok:{token}"),
                InlineKeyboardButton(text="✖️ Bekor", callback_data=f"no:{token}"),
            ]
        ]
    )


# --- Matn formatlash --------------------------------------------------------
def format_task(task: Task, issues: list[rules.Issue]) -> str:
    lines = [
        f"<b>{esc(task.short)}</b>",
        f"{rules.verdict(issues)}  ·  {rules.score(issues)}/100  ·  {esc(task.status)}",
    ]
    meta = []
    if task.assignees:
        meta.append("👤 " + esc(", ".join(task.assignees)))
    if task.deadline:
        meta.append(f"⏰ {task.deadline}")
    elif task.start:
        meta.append(f"📅 {task.start}")
    if meta:
        lines.append("  ".join(meta))
    if issues:
        lines.append("")
        for issue in issues:
            lines.append(f"{issue.icon} {esc(issue.message)}")
    return "\n".join(lines)


async def send_long(chat_id: int, text: str, **kwargs) -> None:
    """4096 belgidan uzun matnni bo'lib yuboradi."""
    limit = 3900
    while text:
        if len(text) <= limit:
            await bot.send_message(chat_id, text, **kwargs)
            return
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        await bot.send_message(chat_id, text[:cut], **kwargs)
        text = text[cut:].lstrip("\n")


# --- Buyruqlar --------------------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "<b>Durust task-menejer</b>\n\n"
        "Men Notion'dagi zadachalarni qoidaga muvofiqligini tekshiraman, "
        "eskirganlari uchun izoh so'rayman va noaniq topshiriqni "
        "konkret zadachaga aylantirib beraman.\n\n"
        "<b>Buyruqlar:</b>\n"
        "/tekshir — barcha aktiv zadachalarni tekshirish\n"
        "/eskirgan — muddati o'tgan zadachalar\n"
        "/yangi <i>matn</i> — noaniq gapdan konkret zadacha yasash\n"
        "/qoidalar — zadacha qoidalari\n"
        "/holat — qisqacha statistika"
    )


@dp.message(Command("qoidalar"))
async def cmd_rules(message: Message) -> None:
    await message.answer(
        "<b>Zadacha qoidalari</b>\n\n"
        "1️⃣ <b>Nom aniq</b> — nima qilinadi + nima ustida + qanday natija.\n"
        f"    Kamida {config.MIN_TITLE_WORDS} so'z, harakat fe'li bilan.\n"
        "2️⃣ <b>Natija o'lchanadigan</b> — raqam, hujjat, ro'yxat, summa.\n"
        "3️⃣ <b>Ijrochi bor</b> — Исполнитель to'ldirilgan.\n"
        "4️⃣ <b>Mas'ul bor</b> — Ответственный to'ldirilgan.\n"
        "5️⃣ <b>Sanalar bor</b> — Дата va Дедлайн qo'yilgan.\n"
        "6️⃣ <b>Deadline mantiqiy</b> — boshlanishdan keyin.\n"
        "7️⃣ <b>Muddati o'tmagan</b> — o'tgan bo'lsa izoh yozilsin.\n"
        f"8️⃣ <b>Qotib qolmagan</b> — «Стрт» da {config.STALE_DAYS} kundan "
        "ko'p turmasin.\n"
        "9️⃣ <b>Noaniq so'z yo'q</b> — «shu», «...», «o'xshagan», «norm».\n"
        "🔟 <b>Bitta zadacha — bitta natija.</b>"
    )


@dp.message(Command("tekshir"))
async def cmd_check(message: Message) -> None:
    if not await notion_guard(message):
        return
    status = await message.answer("⏳ Notion tekshirilyapti...")
    try:
        tasks = await notion.fetch_active_tasks()
    except Exception as exc:
        logger.exception("Notion o'qishda xato")
        await status.edit_text(f"❌ Notion'dan ma'lumot olinmadi:\n<code>{esc(str(exc))}</code>")
        return

    day = today()
    checked = [(t, rules.check_task(t, day)) for t in tasks]
    bad = [(t, i) for t, i in checked if any(x.severity == rules.BLOCKER for x in i)]
    warn = [
        (t, i)
        for t, i in checked
        if i and not any(x.severity == rules.BLOCKER for x in i)
    ]
    clean = [(t, i) for t, i in checked if not i]
    overdue = [(t, i) for t, i in checked if rules.is_overdue(t, day)]

    # Eng ko'p uchraydigan kamchiliklar
    counter: dict[str, int] = {}
    for _, issues in checked:
        for issue in issues:
            counter[issue.message.split(".")[0]] = (
                counter.get(issue.message.split(".")[0], 0) + 1
            )
    top = sorted(counter.items(), key=lambda kv: -kv[1])[:5]

    summary = [
        f"<b>📊 Hisobot — {day}</b>",
        "",
        f"Jami aktiv zadacha: <b>{len(tasks)}</b>",
        f"✅ Qoidaga mos: <b>{len(clean)}</b>",
        f"⚠️ Qisman mos: <b>{len(warn)}</b>",
        f"❌ Mos emas: <b>{len(bad)}</b>",
        f"🔥 Muddati o'tgan: <b>{len(overdue)}</b>",
    ]
    if top:
        summary += ["", "<b>Eng ko'p uchragan kamchiliklar:</b>"]
        summary += [f"• {esc(name)} — {count} ta" for name, count in top]
    await status.edit_text("\n".join(summary))

    storage.save_report(day, len(tasks), len(bad), len(overdue))

    # Eng muammoli 8 tasini alohida ko'rsatamiz
    worst = sorted(bad, key=lambda pair: rules.score(pair[1]))[:8]
    if not worst:
        await message.answer("Blocker darajasidagi muammo yo'q. Barakalla! 👏")
        return
    await message.answer(f"<b>Eng muammoli {len(worst)} ta zadacha:</b>")
    for task, issues in worst:
        await message.answer(
            format_task(task, issues), reply_markup=task_keyboard(task)
        )
        await asyncio.sleep(0.35)


@dp.message(Command("eskirgan"))
async def cmd_overdue(message: Message) -> None:
    if not await notion_guard(message):
        return
    status = await message.answer("⏳ Eskirgan zadachalar qidirilyapti...")
    try:
        tasks = await notion.fetch_active_tasks()
    except Exception as exc:
        await status.edit_text(f"❌ Notion xatosi: <code>{esc(str(exc))}</code>")
        return

    day = today()
    overdue = [(t, rules.overdue_days(t, day)) for t in tasks]
    overdue = sorted(
        [(t, d) for t, d in overdue if d > 0], key=lambda pair: -pair[1]
    )

    if not overdue:
        await status.edit_text("✅ Muddati o'tgan zadacha yo'q.")
        return

    await status.edit_text(
        f"🔥 <b>{len(overdue)} ta zadachaning muddati o'tgan.</b>\n"
        f"Eng eskisidan boshlab 10 tasi:"
    )
    for task, days in overdue[:10]:
        who = ", ".join(task.assignees) or "ijrochi belgilanmagan"
        text = (
            f"<b>{esc(task.short)}</b>\n"
            f"🔥 Muddati <b>{days} kun</b> oldin o'tgan  ·  {esc(task.status)}\n"
            f"👤 {esc(who)}"
        )
        await message.answer(text, reply_markup=task_keyboard(task, overdue=True))
        await asyncio.sleep(0.35)


@dp.message(Command("holat"))
async def cmd_stats(message: Message) -> None:
    if not await notion_guard(message):
        return
    try:
        tasks = await notion.fetch_active_tasks()
    except Exception as exc:
        await message.answer(f"❌ Notion xatosi: <code>{esc(str(exc))}</code>")
        return
    day = today()
    by_status: dict[str, int] = {}
    for task in tasks:
        by_status[task.status] = by_status.get(task.status, 0) + 1
    scores = [rules.score(rules.check_task(t, day)) for t in tasks]
    avg = round(sum(scores) / len(scores)) if scores else 0
    lines = [f"<b>Holat — {day}</b>", "", f"Aktiv zadachalar: <b>{len(tasks)}</b>"]
    lines += [f"  {esc(name)}: {count}" for name, count in sorted(by_status.items())]
    lines += ["", f"O'rtacha sifat balli: <b>{avg}/100</b>"]
    await message.answer("\n".join(lines))


@dp.message(Command("yangi"))
async def cmd_new(message: Message) -> None:
    raw = (message.text or "").partition(" ")[2].strip()
    if not raw:
        await message.answer(
            "Zadacha matnini yozing:\n"
            "<code>/yangi agentlar bilan mikrofon masalasini hal qilish</code>"
        )
        return
    await _clarify_and_offer(message, raw)


async def _clarify_and_offer(message: Message, raw: str) -> None:
    if not await ai_guard(message):
        return
    status = await message.answer("🤔 Zadacha aniqlashtirilyapti...")
    result = await ai.clarify(raw, today())

    if not result.get("ok"):
        questions = result.get("savollar") or ["Zadacha maqsadi nima?"]
        draft_tasks[message.from_user.id] = {"raw": raw}
        await status.edit_text(
            "<b>Zadachani konkret qilish uchun ma'lumot yetmaydi.</b>\n\n"
            + "\n".join(f"❓ {esc(q)}" for q in questions)
            + "\n\n<i>Javobingizni shu yerga yozing — men to'liq zadacha yasab "
            "beraman.</i>"
        )
        return

    deadline = today() + dt.timedelta(days=int(result.get("deadline_kun") or 3))
    token = secrets.token_urlsafe(8)
    proposals[token] = {
        "kind": "create",
        "title": result["nom"],
        "note": result.get("natija", ""),
        "deadline": deadline,
        "user_id": message.from_user.id,
    }
    steps = result.get("qadamlar") or []
    text = [
        "<b>Taklif qilingan zadacha:</b>",
        "",
        f"📌 <b>{esc(result['nom'])}</b>",
        f"🎯 Natija: {esc(result.get('natija', '—'))}",
        f"⏰ Deadline: {deadline}",
    ]
    if steps:
        text += ["", "<b>Qadamlar:</b>"] + [f"{i}. {esc(s)}" for i, s in enumerate(steps, 1)]
    text += ["", "<i>Notion'ga qo'shaymi?</i>"]
    await status.edit_text("\n".join(text), reply_markup=confirm_keyboard(token))


# --- Oddiy matn (izoh yoki aniqlashtirish javobi) ---------------------------
@dp.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message) -> None:
    user_id = message.from_user.id

    # 1) Notion'ga izoh yozish kutilyaptimi
    page_id = awaiting_comment.pop(user_id, None)
    if page_id:
        author = message.from_user.full_name
        text = f"[Telegram · {author}]\n{message.text}"
        ok = await notion.add_comment(page_id, text)
        await message.answer(
            "✅ Izoh Notion'ga yozildi." if ok else "❌ Izoh yozilmadi (huquq yetarli emas?)."
        )
        return

    # 2) Aniqlashtirish savollariga javob berilyaptimi
    draft = draft_tasks.pop(user_id, None)
    if draft:
        combined = f"{draft['raw']}\nQo'shimcha ma'lumot: {message.text}"
        await _clarify_and_offer(message, combined)
        return

    # 3) Guruhda bo'lmasa - erkin matndan zadacha yasab beramiz
    if message.chat.type == "private":
        await _clarify_and_offer(message, message.text)


# --- Tugmalar ---------------------------------------------------------------
@dp.callback_query(F.data.startswith("rev:"))
async def cb_review(call: CallbackQuery) -> None:
    if not config.notion_ready():
        await call.answer("Notion ulanmagan.", show_alert=True)
        return
    await call.answer("Tahlil qilinyapti...")
    page_id = call.data[4:]
    try:
        task = await notion.fetch_task(page_id)
    except Exception as exc:
        await call.message.answer(f"❌ Xato: <code>{esc(str(exc))}</code>")
        return
    issues = rules.check_task(task, today())
    comment = await ai.review(task, issues)
    await call.message.answer(
        f"<b>🔍 {esc(task.short)}</b>\n\n{esc(comment)}\n\n"
        f"<i>{rules.verdict(issues)} · {rules.score(issues)}/100</i>"
    )


@dp.callback_query(F.data.startswith("imp:"))
async def cb_improve(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Sizda Notion'ni o'zgartirish huquqi yo'q.", show_alert=True)
        return
    if not config.notion_ready():
        await call.answer("Notion ulanmagan.", show_alert=True)
        return
    await call.answer("Aniqlashtirilyapti...")
    page_id = call.data[4:]
    try:
        task = await notion.fetch_task(page_id)
    except Exception as exc:
        await call.message.answer(f"❌ Xato: <code>{esc(str(exc))}</code>")
        return

    result = await ai.improve(task)
    if not result.get("nom"):
        await call.message.answer("AI taklif bera olmadi, qaytadan urinib ko'ring.")
        return

    token = secrets.token_urlsafe(8)
    proposals[token] = {
        "kind": "rename",
        "page_id": page_id,
        "title": result["nom"],
        "note": result.get("natija", ""),
        "user_id": call.from_user.id,
    }
    await call.message.answer(
        f"<b>✍️ Aniqlashtirilgan variant</b>\n\n"
        f"<s>{esc(task.short)}</s>\n"
        f"⬇️\n"
        f"📌 <b>{esc(result['nom'])}</b>\n"
        f"🎯 Natija: {esc(result.get('natija', '—'))}\n\n"
        f"<i>{esc(result.get('izoh', ''))}</i>\n\n"
        f"Notion'da almashtiraymi?",
        reply_markup=confirm_keyboard(token),
    )


@dp.callback_query(F.data.startswith("ask:"))
async def cb_ask(call: CallbackQuery) -> None:
    if not config.notion_ready():
        await call.answer("Notion ulanmagan.", show_alert=True)
        return
    await call.answer("Izoh so'ralyapti...")
    page_id = call.data[4:]
    try:
        task = await notion.fetch_task(page_id)
    except Exception as exc:
        await call.message.answer(f"❌ Xato: <code>{esc(str(exc))}</code>")
        return
    days = rules.overdue_days(task, today())
    text = await ai.ask_stale(task, days)
    ok = await notion.add_comment(page_id, f"[Task-bot]\n{text}")
    who = ", ".join(task.assignees) or "ijrochi"
    await call.message.answer(
        f"<b>📩 {esc(who)} uchun so'rov</b>\n\n{esc(text)}\n\n"
        + ("<i>Notion sahifasiga ham yozildi.</i>" if ok else
           "<i>⚠️ Notion'ga yozilmadi — integratsiyada komentariya huquqi yo'q.</i>")
    )


@dp.callback_query(F.data.startswith("com:"))
async def cb_comment(call: CallbackQuery) -> None:
    if not config.notion_ready():
        await call.answer("Notion ulanmagan.", show_alert=True)
        return
    page_id = call.data[4:]
    awaiting_comment[call.from_user.id] = page_id
    await call.answer()
    hint = (
        "shu xabarga <b>reply</b> qilib yozing"
        if call.message.chat.type != "private"
        else "izohingizni shu yerga yozing"
    )
    await call.message.answer(
        f"💬 {esc(call.from_user.full_name)}, {hint} — "
        f"men uni Notion sahifasiga qo'shaman."
    )


@dp.callback_query(F.data.startswith("ok:"))
async def cb_confirm(call: CallbackQuery) -> None:
    token = call.data[3:]
    proposal = proposals.pop(token, None)
    if not proposal:
        await call.answer("Bu taklif eskirgan.", show_alert=True)
        return
    if not is_admin(call.from_user.id):
        await call.answer("Huquq yo'q.", show_alert=True)
        return
    await call.answer("Saqlanyapti...")

    if proposal["kind"] == "create":
        url = await notion.create_task(
            title=proposal["title"],
            start=today(),
            deadline=proposal["deadline"],
            note=proposal["note"],
        )
        if url:
            await call.message.edit_text(
                f"✅ <b>Notion'ga qo'shildi</b>\n\n📌 {esc(proposal['title'])}\n"
                f"⏰ {proposal['deadline']}\n\n<a href=\"{url}\">Notion'da ochish</a>"
            )
        else:
            await call.message.answer("❌ Yaratilmadi. Loglarni tekshiring.")
    else:
        ok = await notion.update_title(proposal["page_id"], proposal["title"])
        if ok:
            await notion.add_comment(
                proposal["page_id"],
                f"[Task-bot] Zadacha nomi aniqlashtirildi.\n"
                f"Kutilayotgan natija: {proposal['note']}",
            )
            await call.message.edit_text(
                f"✅ <b>Yangilandi</b>\n\n📌 {esc(proposal['title'])}"
            )
        else:
            await call.message.answer("❌ Yangilanmadi. Loglarni tekshiring.")


@dp.callback_query(F.data.startswith("no:"))
async def cb_cancel(call: CallbackQuery) -> None:
    proposals.pop(call.data[3:], None)
    await call.answer("Bekor qilindi")
    await call.message.edit_text("✖️ Bekor qilindi.")


# --- Kunlik avtomatik hisobot ----------------------------------------------
async def daily_report() -> None:
    if not config.GROUP_CHAT_ID:
        logger.warning("GROUP_CHAT_ID yo'q, kunlik hisobot yuborilmadi")
        return
    if not config.notion_ready():
        logger.warning("NOTION_TOKEN yo'q, kunlik hisobot o'tkazib yuborildi")
        return
    day = today()
    logger.info("Kunlik hisobot boshlandi: %s", day)
    try:
        tasks = await notion.fetch_active_tasks()
    except Exception:
        logger.exception("Kunlik hisobot: Notion xatosi")
        return

    checked = [(t, rules.check_task(t, day)) for t in tasks]
    bad = [(t, i) for t, i in checked if any(x.severity == rules.BLOCKER for x in i)]
    overdue = sorted(
        [(t, rules.overdue_days(t, day)) for t in tasks if rules.is_overdue(t, day)],
        key=lambda pair: -pair[1],
    )

    await bot.send_message(
        config.GROUP_CHAT_ID,
        f"<b>☀️ Kunlik tekshiruv — {day}</b>\n\n"
        f"Aktiv zadachalar: <b>{len(tasks)}</b>\n"
        f"❌ Qoidaga mos emas: <b>{len(bad)}</b>\n"
        f"🔥 Muddati o'tgan: <b>{len(overdue)}</b>\n\n"
        f"<i>Batafsil: /tekshir va /eskirgan</i>",
    )
    storage.save_report(day, len(tasks), len(bad), len(overdue))

    # Muddati o'tganlar uchun izoh so'raymiz (kuniga bir marta har zadacha uchun)
    sent = 0
    for task, days in overdue:
        if sent >= 5:
            break
        if storage.already_notified(task.page_id, "overdue", day):
            continue
        text = await ai.ask_stale(task, days)
        if config.WRITE_TO_NOTION:
            await notion.add_comment(task.page_id, f"[Task-bot]\n{text}")
        who = ", ".join(task.assignees) or "ijrochi"
        await bot.send_message(
            config.GROUP_CHAT_ID,
            f"<b>🔥 {esc(task.short)}</b>\n"
            f"👤 {esc(who)} · muddati {days} kun oldin o'tgan\n\n{esc(text)}",
            reply_markup=task_keyboard(task, overdue=True),
        )
        storage.mark_notified(task.page_id, "overdue", day)
        sent += 1
        await asyncio.sleep(0.5)

    storage.cleanup()
    logger.info("Kunlik hisobot tugadi")


# --- Ishga tushirish --------------------------------------------------------
async def on_startup() -> None:
    config.validate()
    storage.init()
    await bot.set_my_commands(
        [
            BotCommand(command="tekshir", description="Zadachalarni tekshirish"),
            BotCommand(command="eskirgan", description="Muddati o'tganlar"),
            BotCommand(command="yangi", description="Konkret zadacha yasash"),
            BotCommand(command="qoidalar", description="Zadacha qoidalari"),
            BotCommand(command="holat", description="Statistika"),
        ]
    )
    missing = config.missing_optional()
    if missing:
        logger.warning(
            "Ishlamaydigan imkoniyatlar bor - .env da yo'q: %s", ", ".join(missing)
        )

    if config.notion_ready():
        try:
            await notion.load_users()
            database_id = await notion.resolve_database_id()
            logger.info("Notion tayyor. Baza: %s", database_id)
        except Exception as exc:
            logger.error("Notion ulanmadi: %s", exc)
    else:
        logger.warning(
            "NOTION_TOKEN yo'q: /tekshir, /eskirgan, /holat ishlamaydi. "
            "Ulash uchun: python notion_token.py"
        )

    if not config.ai_ready():
        logger.warning("OPENAI_API_KEY yo'q: /yangi va AI komentariyalar o'chiq")


async def main() -> None:
    await on_startup()
    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(
        daily_report,
        CronTrigger(hour=config.REPORT_HOUR, minute=config.REPORT_MINUTE),
        id="daily_report",
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info(
        "Bot ishga tushdi. Kunlik hisobot %02d:%02d (%s)",
        config.REPORT_HOUR,
        config.REPORT_MINUTE,
        config.TIMEZONE,
    )
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await notion.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi")
