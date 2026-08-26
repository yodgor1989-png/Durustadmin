"""Kalkulyator Telegram bot (aiogram 3).

Ishga tushirish:
    1) .env faylida BOT_TOKEN ni yozing
    2) pip install -r requirements.txt
    3) python bot.py
"""

import asyncio
import html
import logging
import os
from collections import defaultdict, deque

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
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from calculator import CalcError, calculate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("calc-bot")

# --- Holat (xotirada saqlanadi) ---------------------------------------------
# Har bir foydalanuvchining tugmali kalkulyatordagi joriy ifodasi
screens = defaultdict(str)
# Har bir foydalanuvchining oxirgi 10 ta hisobi
history = defaultdict(lambda: deque(maxlen=10))

MAX_SCREEN_LEN = 60


# --- Klaviaturalar ----------------------------------------------------------
def calc_keyboard():
    """Tugmali kalkulyator (inline klaviatura)."""
    rows = [
        ["C", "( )", "%", "/"],
        ["7", "8", "9", "*"],
        ["4", "5", "6", "-"],
        ["1", "2", "3", "+"],
        ["0", ".", "DEL", "="],
    ]
    keyboard = []
    for row in rows:
        keyboard.append([
            InlineKeyboardButton(text=_label(key), callback_data="k:" + key)
            for key in row
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _label(key):
    """Tugma yozuvini chiroyliroq ko'rsatish."""
    return {"DEL": "⌫", "*": "×", "/": "÷"}.get(key, key)


def main_keyboard():
    """Pastdagi doimiy menyu."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="\U0001f9ee Kalkulyator"), KeyboardButton(text="\U0001f4dc Tarix")],
            [KeyboardButton(text="ℹ️ Yordam")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Ifodani yozing, masalan: 12*(3+4)",
    )


# --- Matnlar ----------------------------------------------------------------
WELCOME = (
    "\U0001f44b <b>Salom, {name}!</b>\n\n"
    "Men <b>kalkulyator botman</b>. Menga matematik ifoda yuboring - "
    "men uni hisoblab beraman.\n\n"
    "<b>Masalan:</b>\n"
    "<code>2 + 2 * 3</code>\n"
    "<code>(15 + 5) / 4</code>\n"
    "<code>sqrt(144)</code>\n"
    "<code>2^10</code>\n"
    "<code>25% * 200</code>\n\n"
    "Yoki /calc buyrug'i bilan tugmali kalkulyatorni oching."
)

HELP = (
    "ℹ️ <b>Yordam</b>\n\n"
    "<b>Amallar:</b>\n"
    "<code>+</code> qo'shish, <code>-</code> ayirish\n"
    "<code>*</code> yoki <code>×</code> ko'paytirish\n"
    "<code>/</code> yoki <code>÷</code> bo'lish\n"
    "<code>//</code> butun bo'lish, <code>%</code> qoldiq\n"
    "<code>^</code> yoki <code>**</code> daraja\n"
    "<code>( )</code> qavslar\n\n"
    "<b>Funksiyalar:</b>\n"
    "<code>sqrt(x)</code> kvadrat ildiz, <code>cbrt(x)</code> kub ildiz\n"
    "<code>abs(x)</code>, <code>round(x, n)</code>, <code>min(...)</code>, <code>max(...)</code>\n"
    "<code>floor(x)</code>, <code>ceil(x)</code>, <code>factorial(n)</code>\n"
    "<code>log(x)</code>, <code>log10(x)</code>, <code>log2(x)</code>, <code>exp(x)</code>\n"
    "<code>sin(x)</code>, <code>cos(x)</code>, <code>tan(x)</code> - radianda\n"
    "<code>radians(x)</code>, <code>degrees(x)</code>\n"
    "<code>gcd(a,b)</code> EKUB, <code>lcm(a,b)</code> EKUK\n\n"
    "<b>Doimiylar:</b> <code>pi</code>, <code>e</code>, <code>tau</code>\n\n"
    "<b>Buyruqlar:</b>\n"
    "/start - boshlash\n"
    "/calc - tugmali kalkulyator\n"
    "/history - oxirgi hisoblar\n"
    "/clear - tarixni tozalash\n"
    "/help - shu yordam\n\n"
    "<b>Misollar:</b>\n"
    "<code>(2+3)*4-10/5</code> → 18\n"
    "<code>sqrt(16)+2^5</code> → 36\n"
    "<code>factorial(5)</code> → 120\n"
    "<code>sin(pi/2)</code> → 1"
)


def screen_text(expr):
    """Tugmali kalkulyator ekrani matni."""
    shown = expr if expr else "0"
    return (
        "\U0001f9ee <b>Kalkulyator</b>\n\n"
        "<pre>" + html.escape(shown) + "</pre>\n"
        "<i>Tugmalarni bosing yoki ifodani matn qilib yuboring.</i>"
    )


# --- Bot --------------------------------------------------------------------
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    name = html.escape(message.from_user.first_name or "do'stim")
    await message.answer(WELCOME.format(name=name), reply_markup=main_keyboard())


@dp.message(Command("help"))
@dp.message(F.text == "ℹ️ Yordam")
async def cmd_help(message: Message):
    await message.answer(HELP)


@dp.message(Command("calc"))
@dp.message(F.text == "\U0001f9ee Kalkulyator")
async def cmd_calc(message: Message):
    screens[message.from_user.id] = ""
    await message.answer(screen_text(""), reply_markup=calc_keyboard())


@dp.message(Command("history"))
@dp.message(F.text == "\U0001f4dc Tarix")
async def cmd_history(message: Message):
    items = history[message.from_user.id]
    if not items:
        await message.answer("\U0001f4dc Tarix bo'sh. Biror ifoda yuboring!")
        return
    lines = ["\U0001f4dc <b>Oxirgi hisoblar:</b>\n"]
    for i, (expr, result) in enumerate(items, 1):
        lines.append(
            "%d. <code>%s</code> = <b>%s</b>"
            % (i, html.escape(expr), html.escape(result))
        )
    await message.answer("\n".join(lines))


@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    history[message.from_user.id].clear()
    screens[message.from_user.id] = ""
    await message.answer("\U0001f9f9 Tarix tozalandi.")


@dp.message(F.text)
async def handle_expression(message: Message):
    """Oddiy matn - uni ifoda deb hisoblaymiz."""
    expr = message.text.strip()
    try:
        result = calculate(expr)
    except CalcError as exc:
        await message.answer(
            "❌ <b>Xato:</b> %s\n\n"
            "To'g'ri yozilishiga misol: <code>2 + 2 * 3</code>\n"
            "Barcha imkoniyatlar: /help" % html.escape(str(exc))
        )
        return
    except RecursionError:
        await message.answer("❌ Ifoda juda murakkab.")
        return
    except Exception:
        logger.exception("Kutilmagan xato, ifoda: %r", expr)
        await message.answer("❌ Kutilmagan xato yuz berdi. Qaytadan urinib ko'ring.")
        return

    history[message.from_user.id].append((expr, result))
    await message.answer(
        "\U0001f9ee <code>%s</code>\n= <b>%s</b>"
        % (html.escape(expr), html.escape(result))
    )


@dp.message()
async def handle_other(message: Message):
    await message.answer(
        "Men faqat matn ko'rinishidagi matematik ifodalarni tushunaman.\n"
        "Masalan: <code>12 * (3 + 4)</code>"
    )


@dp.callback_query(F.data.startswith("k:"))
async def handle_button(call: CallbackQuery):
    """Tugmali kalkulyator tugmalari."""
    user_id = call.from_user.id
    key = call.data[2:]
    expr = screens[user_id]
    notice = None

    if key == "C":
        expr = ""
    elif key == "DEL":
        expr = expr[:-1]
    elif key == "( )":
        # Ochilmagan qavs bo'lsa yopamiz, aks holda yangi qavs ochamiz
        opened = expr.count("(") - expr.count(")")
        last = expr[-1] if expr else ""
        if opened > 0 and (last.isdigit() or last in ").%"):
            expr += ")"
        else:
            expr += "("
    elif key == "=":
        if not expr:
            await call.answer("Avval ifoda kiriting")
            return
        try:
            result = calculate(expr)
        except CalcError as exc:
            await call.answer("❌ " + str(exc), show_alert=True)
            return
        except Exception:
            logger.exception("Tugmali kalkulyatorda xato: %r", expr)
            await call.answer("❌ Kutilmagan xato", show_alert=True)
            return

        history[user_id].append((expr, result))
        screens[user_id] = ""
        await call.message.edit_text(
            "\U0001f9ee <code>%s</code>\n= <b>%s</b>\n\n<i>Yangi hisob uchun tugmalarni bosing.</i>"
            % (html.escape(expr), html.escape(result)),
            reply_markup=calc_keyboard(),
        )
        await call.answer("= " + result)
        return
    else:
        if len(expr) >= MAX_SCREEN_LEN:
            await call.answer("Ifoda juda uzun", show_alert=True)
            return
        expr += key

    screens[user_id] = expr

    new_text = screen_text(expr)
    if new_text != (call.message.html_text if call.message.text else None):
        try:
            await call.message.edit_text(new_text, reply_markup=calc_keyboard())
        except Exception:
            # "message is not modified" kabi xatolarni e'tiborsiz qoldiramiz
            pass
    await call.answer(notice or "")


# Telegramdagi "/" menyusida ko'rinadigan buyruqlar
BOT_COMMANDS = [
    BotCommand(command="start", description="Botni boshlash"),
    BotCommand(command="calc", description="Tugmali kalkulyator"),
    BotCommand(command="history", description="Oxirgi hisoblar"),
    BotCommand(command="clear", description="Tarixni tozalash"),
    BotCommand(command="help", description="Yordam va funksiyalar"),
]


def read_token():
    """BOT_TOKEN ni muhit o'zgaruvchisidan yoki yondagi .env faylidan o'qiydi."""
    token = os.getenv("BOT_TOKEN", "").strip()
    if token:
        return token

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        # python-dotenv yo'q bo'lsa - .env ni o'zimiz o'qiymiz
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("BOT_TOKEN=") and not line.startswith("#"):
                        return line.split("=", 1)[1].strip().strip("'\"")
    return os.getenv("BOT_TOKEN", "").strip()


async def main():
    token = read_token()
    if not token:
        raise SystemExit(
            "BOT_TOKEN topilmadi!\n"
            "1) @BotFather dan token oling\n"
            "2) .env faylini yarating va ichiga yozing:  BOT_TOKEN=123456:ABC...\n"
            "   yoki muhit o'zgaruvchisini o'rnating:    set BOT_TOKEN=123456:ABC..."
        )

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    logger.info("Bot ishga tushdi: @%s", me.username)

    await bot.set_my_commands(BOT_COMMANDS)
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as exc:
        if isinstance(exc, SystemExit) and exc.code:
            raise
        logger.info("Bot to'xtatildi.")
