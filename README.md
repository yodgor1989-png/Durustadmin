# Durust task-menejer boti

Notion'dagi **"Durust задача дашборд"** bazasini kuzatib turadigan Telegram bot.

Nima qiladi:

1. **Qoidaga muvofiqligini tekshiradi** — har bir zadachani 12 ta qoida
   bo'yicha baholab, 0–100 ball va aniq kamchiliklar ro'yxatini beradi.
2. **Eskirgan zadachalar uchun izoh so'raydi** — muddati o'tgan zadacha
   ijrochisidan "nima qilindi, nima to'sqinlik qildi, yangi muddat qachon"
   deb so'raydi va javobni Notion sahifasiga komentariya qilib yozadi.
3. **Masalani aniqlashtiradi** — noaniq gapdan konkret zadacha yozib beradi;
   ma'lumot yetmasa, avval aniqlovchi savol beradi. Tasdiqlasangiz Notion'ga
   qo'shadi.

---

## 1. O'rnatish

```bash
pip install -r requirements.txt
```

## 2. `.env` ni to'ldirish

`.env.example` dan nusxa oling va quyidagilarni to'ldiring:

| Kalit | Qayerdan olinadi |
|---|---|
| `BOT_TOKEN` | @BotFather → botni tanlang → API Token |
| `NOTION_TOKEN` | https://www.notion.so/my-integrations → **New integration** → Internal Integration Secret |
| `NOTION_DATABASE_ID` | Baza URL'idagi uzun hex qism: `notion.so/<workspace>/<BAZA_ID>?v=...` |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `GROUP_CHAT_ID` | Kunlik hisobot yuboriladigan guruh ID |

Tokenni qo'lda yozish o'rniga yordamchi skriptdan foydalanish qulayroq —
u tokenni tekshirib, faqat ishlasa `.env` ga yozadi:

```bash
python notion_token.py
```

### Notion integratsiyasini ulash (majburiy)

Token yetarli emas — integratsiyani sahifaga **ulash** kerak:

1. https://www.notion.so/my-integrations → **New integration** → nom bering.
2. Capabilities'da yoqing: **Read content**, **Update content**,
   **Insert content**, **Read comments**, **Insert comments**,
   **Read user information**.
3. "Internal Integration Secret" ni nusxalab `.env` ga qo'ying.
4. Notion'da **Management** sahifasini oching → o'ng yuqoridagi `...` →
   **Connections** → yaratgan integratsiyangizni qo'shing.

Ulanmasa bot `401 Unauthorized` yoki `object_not_found` xatosini beradi.

## 3. Tekshirish

```bash
python check.py
```

Uchala ulanishni sinaydi va nima yetishmayotganini aytadi.

## 4. Ishga tushirish

```bash
python main.py
```

Yoki `start.bat` faylini ikki marta bosing.

---

## Buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `/tekshir` | Barcha aktiv zadachalarni tekshirib hisobot beradi |
| `/eskirgan` | Muddati o'tgan zadachalar + izoh so'rash tugmalari |
| `/yangi <matn>` | Noaniq gapdan konkret zadacha yasaydi |
| `/qoidalar` | Zadacha qoidalarini ko'rsatadi |
| `/holat` | Qisqacha statistika |

Shaxsiy chatda buyruqsiz matn yozsangiz ham bot uni zadachaga aylantirishga
harakat qiladi.

### Tugmalar

- **🔍 Tahlil** — zadacha bo'yicha batafsil komentariya
- **✍️ Aniqlashtirish** — AI yaxshilangan nom taklif qiladi, tasdiqlasangiz
  Notion'da almashtiradi
- **📩 Izoh so'rash** — ijrochidan hisobot so'raydi va Notion'ga yozadi
- **💬 Izoh yozish** — sizning izohingizni Notion sahifasiga qo'shadi

---

## Zadacha qoidalari

| # | Qoida | Daraja |
|---|---|---|
| 1 | Nom yozilgan bo'lsin | 🔴 blocker |
| 2 | Nom kamida `MIN_TITLE_WORDS` so'z | 🔴 blocker |
| 3 | Nom tugallangan (`...` bilan tugamasin) | 🔴 blocker |
| 4 | Noaniq so'z yo'q (`shu`, `o'xshagan`, `norm`) | 🟡 warning |
| 5 | Aniq harakat fe'li bor | 🟡 warning |
| 6 | Ijrochi (Исполнитель) belgilangan | 🔴 blocker |
| 7 | Mas'ul (Ответственный) belgilangan | 🟡 warning |
| 8 | Boshlanish sanasi (Дата) bor | 🟡 warning |
| 9 | Deadline bor | 🔴 blocker |
| 10 | Deadline boshlanishdan keyin | 🔴 blocker |
| 11 | Muddati o'tmagan | 🔴 blocker |
| 12 | «Стрт» da `STALE_DAYS` kundan ko'p qotib qolmagan | 🟡 warning |

**Ball:** 100 dan boshlanadi, har blocker −20, har warning −7.

**Takrorlanuvchi hisobotlar** (nomida «Кунлик», «Хафталик», «очет» va
shunga o'xshash so'z bo'lganlar) shablon hisoblanadi: ularga 2, 5-qoida
qo'llanmaydi, 9-qoida esa faqat ogohlantirish bo'ladi.

Qoidalarni `.env` orqali sozlash mumkin: `MIN_TITLE_WORDS`, `STALE_DAYS`.

---

## Kunlik avtomatik hisobot

Har kuni `REPORT_HOUR:REPORT_MINUTE` (default 09:00, Toshkent vaqti) da
`GROUP_CHAT_ID` guruhiga:

- umumiy statistika,
- muddati eng ko'p o'tgan 5 ta zadacha va ularga izoh so'rovi.

Bitta zadacha uchun kuniga bir marta so'raladi (`bot_state.db` da eslab
qolinadi).

---

## Fayllar

```
main.py            ishga tushirish
check.py           ulanishlarni tekshirish
demo.py            Notion'siz namoyish (haqiqiy ma'lumot namunasi ustida)
test_rules.py      qoidalar testi (24 ta tekshiruv)
app/config.py      .env sozlamalari
app/notion.py      Notion API klienti
app/rules.py       qoidalar dvigateli
app/ai.py          OpenAI qatlami
app/bot.py         Telegram handlerlar + kunlik hisobot
app/storage.py     SQLite (takroriy xabarni oldini olish)
_old_calculator/   eski kalkulyator bot (ishlatilmaydi)
```

## Eslatmalar

- **AI ishlamasa bot to'xtamaydi.** OpenAI xatosi bo'lsa komentariya
  o'rniga qoidalar ro'yxati chiqadi — tekshiruv baribir ishlaydi.
- **Guruhda privacy rejimi.** Bot guruhda faqat buyruqlar va o'ziga
  qilingan reply'larni ko'radi. "Izoh yozish" tugmasidan keyin bot xabariga
  **reply** qilib yozing. Yoki BotFather → `/setprivacy` → **Disable**.
- **Notion'ga yozishni o'chirish:** `.env` da `WRITE_TO_NOTION=false`.
  Shunda bot faqat Telegram'da gapiradi, Notion'ga tegmaydi.
- **Kim o'zgartira oladi:** `ADMIN_IDS` bo'sh bo'lsa — hamma. Cheklash uchun
  Telegram ID'larni vergul bilan yozing.
