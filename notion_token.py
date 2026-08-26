"""Notion tokenini .env ga qo'yish yordamchisi: python notion_token.py

Tokenni so'raydi, haqiqiyligini tekshiradi, bazaga kirish borligini
sinaydi va faqat hammasi joyida bo'lsa .env ga yozadi.
"""

import os
import re
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)
DB_ID = os.getenv("NOTION_DATABASE_ID", "").replace("-", "")
API = "https://api.notion.com/v1"


def headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def clean(raw: str) -> str:
    """Ortiqcha tirnoq, bo'shliq va 'NOTION_TOKEN=' prefiksini olib tashlaydi."""
    value = raw.strip()
    if "=" in value and value.lower().startswith("notion_token"):
        value = value.split("=", 1)[1]
    return value.strip().strip('"').strip("'").strip()


def check_auth(token: str) -> tuple[bool, str]:
    """Token haqiqiymi."""
    try:
        resp = httpx.get(f"{API}/users?page_size=1", headers=headers(token), timeout=25)
    except Exception as exc:
        return False, f"Internetga ulanib bo'lmadi: {exc}"
    if resp.status_code == 401:
        return False, "Token noto'g'ri (401). Secret'ni qaytadan nusxalang."
    if resp.status_code >= 400:
        return False, f"Xato {resp.status_code}: {resp.text[:150]}"
    return True, "Token haqiqiy"


def check_database(token: str) -> tuple[bool, str]:
    """Integratsiya bazaga ulanganmi."""
    try:
        resp = httpx.post(
            f"{API}/databases/{DB_ID}/query",
            headers=headers(token),
            json={"page_size": 1},
            timeout=25,
        )
    except Exception as exc:
        return False, f"So'rov ketmadi: {exc}"
    if resp.status_code == 404:
        return False, (
            "Baza ko'rinmayapti (404).\n"
            "      Integratsiya sahifaga ULANMAGAN. Notion'da 'Management'\n"
            "      sahifasini oching -> o'ng yuqorida '...' -> Connections\n"
            "      -> integratsiyangizni qo'shing. Keyin qayta urinib ko'ring."
        )
    if resp.status_code >= 400:
        return False, f"Xato {resp.status_code}: {resp.text[:200]}"
    return True, "Baza o'qildi"


def check_comments(token: str) -> tuple[bool, str]:
    """Komentariya o'qish huquqi bormi (yozish huquqi shu bilan birga keladi)."""
    try:
        resp = httpx.get(
            f"{API}/comments?block_id={DB_ID}", headers=headers(token), timeout=25
        )
    except Exception:
        return False, "tekshirib bo'lmadi"
    if resp.status_code == 403:
        return False, (
            "Komentariya huquqi yo'q.\n"
            "      Integratsiya sozlamalarida 'Read comments' va\n"
            "      'Insert comments' ni yoqing. Busiz bot Notion'ga izoh\n"
            "      yoza olmaydi (qolgan hammasi ishlayveradi)."
        )
    return True, "Komentariya huquqi bor"


def write_env(token: str) -> None:
    text = ENV_PATH.read_text(encoding="utf-8")
    if re.search(r"^NOTION_TOKEN=.*$", text, flags=re.MULTILINE):
        text = re.sub(
            r"^NOTION_TOKEN=.*$", f"NOTION_TOKEN={token}", text, flags=re.MULTILINE
        )
    else:
        text = text.rstrip("\n") + f"\nNOTION_TOKEN={token}\n"
    ENV_PATH.write_text(text, encoding="utf-8")


def main() -> int:
    print("\n=== Notion tokenini o'rnatish ===\n")
    print("Token qayerdan olinadi:")
    print("  1. https://www.notion.so/my-integrations -> New integration")
    print("  2. Capabilities: Read/Update/Insert content,")
    print("     Read/Insert comments, Read user information")
    print("  3. 'Internal Integration Secret' -> Show -> nusxalang")
    print("  4. Notion'da 'Management' sahifasi -> '...' -> Connections")
    print("     -> integratsiyani ulang\n")

    if len(sys.argv) > 1:
        token = clean(sys.argv[1])
    else:
        token = clean(input("Tokenni shu yerga tashlang (ntn_...): "))

    if not token:
        print("\n[XATO] Token kiritilmadi.\n")
        return 1
    if not token.startswith(("ntn_", "secret_")):
        print(
            f"\n[?] Token 'ntn_' bilan boshlanmayapti ({token[:6]}...).\n"
            "    Baribir tekshirib ko'raman.\n"
        )

    print()
    ok, msg = check_auth(token)
    print(f"{'[OK]  ' if ok else '[XATO]'} Autentifikatsiya - {msg}")
    if not ok:
        print("\n.env o'zgartirilmadi.\n")
        return 1

    if not DB_ID:
        print(
            "[?]    Bazaga kirish - NOTION_DATABASE_ID .env da yo'q, "
            "tekshirib bo'lmadi.\n"
            "       Baza URL'idan oling: notion.so/<workspace>/<BAZA_ID>?v=..."
        )
    else:
        ok, msg = check_database(token)
        print(f"{'[OK]  ' if ok else '[XATO]'} Bazaga kirish - {msg}")
        if not ok:
            print("\n.env o'zgartirilmadi.\n")
            return 1

        ok_c, msg_c = check_comments(token)
        print(f"{'[OK]  ' if ok_c else '[?]   '} Komentariya - {msg_c}")

    write_env(token)
    print(f"\n[OK]   .env yangilandi: {ENV_PATH}")
    print("\nEndi:  python check.py     (to'liq tekshiruv)")
    print("So'ng: python main.py      (botni ishga tushirish)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
