"""Botni ishga tushirish nuqtasi: python main.py"""

import asyncio
import sys

from app import config

if __name__ == "__main__":
    try:
        config.validate()
    except RuntimeError as exc:
        print(f"\n[SOZLAMA XATOSI] {exc}\n")
        print("Ulanishlarni tekshirish uchun:  python check.py\n")
        sys.exit(1)

    from app.bot import main

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot to'xtatildi")
