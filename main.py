import os
import re
import httpx
import uvicorn
from fastapi import FastAPI, Request
from openai import AsyncOpenAI


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OWNER_ID = os.getenv("OWNER_ID")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN yo'q")

if not OPENAI_KEY:
    raise RuntimeError("OPENAI_API_KEY yo'q")

if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL yo'q")


app = FastAPI()
ai = AsyncOpenAI(api_key=OPENAI_KEY)
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Render restart bo'lsa, bu xotira tozalanadi.
CHAT_STATE = {}


def get_state(chat_id):
    if chat_id not in CHAT_STATE:
        CHAT_STATE[chat_id] = {
            "language": None,
            "introduced": False,
            "asked_name": False,
            "name": None
        }
    return CHAT_STATE[chat_id]


def _contains_word(text, words):
    """Word-boundary matching so short words like 'ha' don't match inside
    unrelated words like 'chat' or 'what'."""
    for w in words:
        if re.search(r"\b" + re.escape(w) + r"\b", text):
            return True
    return False


def detect_language(text):
    t = text.lower().strip()

    if re.search(r"[а-яё]", t):
        return "ru"

    english_words = [
        "hello", "hi", "hey", "how are you", "what", "why", "where",
        "when", "please", "thanks", "thank you", "english", "help me",
        "can you", "could you", "my name is", "i am", "good morning",
        "good evening"
    ]

    russian_latin_words = [
        "privet", "zdravstvuy", "spasibo", "kak dela", "russki",
        "po russki", "russian"
    ]

    uzbek_words = [
        "salom", "assalomu", "qalaysiz", "qalesiz", "rahmat", "iltimos",
        "nima", "qanday", "nega", "ismim", "yordam", "xabar",
        "yaxshimisiz", "ha", "yo'q", "yoq"
    ]

    if _contains_word(t, english_words):
        return "en"

    if _contains_word(t, russian_latin_words):
        return "ru"

    if _contains_word(t, uzbek_words):
        return "uz"

    if re.search(r"\b(i|you|we|they|he|she|it|is|are|am|the|a|an|to|for|with|from|this|that)\b", t):
        return "en"

    return "uz"


def detect_language_change(text):
    t = text.lower().strip()

    if any(x in t for x in [
        "ruscha", "rus tilida", "russian", "по-русски", "на русском",
        "говори по русски", "пиши на русском"
    ]):
        return "ru"

    if any(x in t for x in [
        "inglizcha", "ingliz tilida", "english", "in english",
        "speak english", "write english", "write in english"
    ]):
        return "en"

    if any(x in t for x in [
        "o'zbekcha", "o‘zbekcha", "uzbekcha", "uzbek", "o'zbek tilida",
        "o‘zbek tilida", "write in uzbek"
    ]):
        return "uz"

    return None


def intro_text(lang):
    if lang == "ru":
        return "Здравствуйте, я NOVA. Чем могу помочь? Как вас зовут?"
    if lang == "en":
        return "Hi, I’m NOVA. How can I help? What’s your name?"
    return "Salom, NOVA man. Qanday yordam bera olaman? Ismingiz nima?"


def start_text():
    return (
        "Salom, NOVA man. Qanday yordam bera olaman?\n\n"
        "Hi, I’m NOVA. How can I help?\n\n"
        "Здравствуйте, я NOVA. Чем могу помочь?"
    )


def language_changed_text(lang):
    if lang == "ru":
        return "Хорошо, продолжим на русском."
    if lang == "en":
        return "Sure, we’ll continue in English."
    return "Mayli, o‘zbek tilida davom etamiz."


def extract_name(text):
    t = text.strip()

    patterns = [
        r"mening ismim\s+([A-Za-zА-Яа-яЁёʻʼ‘’`'\-]+)",
        r"meni ismim\s+([A-Za-zА-Яа-яЁёʻʼ‘’`'\-]+)",
        r"ismim\s+([A-Za-zА-Яа-яЁёʻʼ‘’`'\-]+)",
        r"men\s+([A-Za-zА-Яа-яЁёʻʼ‘’`'\-]+)man",
        r"my name is\s+([A-Za-zА-Яа-яЁёʻʼ‘’`'\-]+)",
        r"i am\s+([A-Za-zА-Яа-яЁёʻʼ‘’`'\-]+)",
        r"i'm\s+([A-Za-zА-Яа-яЁёʻʼ‘’`'\-]+)",
        r"меня зовут\s+([A-Za-zА-Яа-яЁёʻʼ‘’`'\-]+)",
        r"я\s+([A-Za-zА-Яа-яЁёʻʼ‘’`'\-]+)"
    ]

    for p in patterns:
        m = re.search(p, t, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if len(name) > 1:
                return name[:1].upper() + name[1:]

    return None


def wants_to_leave_message(text):
    t = text.lower().strip()

    keywords = [
        "xabar yetkaz",
        "xabar yetkazib",
        "yetkazib qo'y",
        "yetkazib qoy",
        "egasiga ayt",
        "adminga ayt",
        "unga ayt",
        "xabar qoldir",
        "xabarimni yetkaz",
        "shu xabarni yetkaz",
        "message to owner",
        "tell admin",
        "tell owner",
        "tell him",
        "tell her",
        "leave a message",
        "forward this message",
        "передай",
        "сообщи",
        "оставь сообщение",
        "оставить сообщение",
        "скажи владельцу",
        "передай владельцу"
    ]

    return any(k in t for k in keywords)


def clean_left_message(text):
    cleaned = text.strip()

    separators = [":", "-", "—"]
    for sep in separators:
        if sep in cleaned:
            parts = cleaned.split(sep, 1)
            if len(parts[1].strip()) > 2:
                return parts[1].strip()

    remove_phrases = [
        "xabar yetkazib qo'y",
        "xabar yetkazib qoy",
        "xabar yetkaz",
        "egasiga ayt",
        "adminga ayt",
        "xabar qoldir",
        "tell admin",
        "tell owner",
        "leave a message",
        "передай",
        "сообщи",
        "скажи владельцу"
    ]

    low = cleaned.lower()
    for phrase in remove_phrases:
        if phrase in low:
            idx = low.find(phrase)
            result = cleaned[idx + len(phrase):].strip()
            if result:
                return result

    return cleaned


async def send_msg(chat_id, text, business_id=None):
    if not text:
        return

    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]

    async with httpx.AsyncClient(timeout=30) as client:
        for chunk in chunks:
            data = {
                "chat_id": chat_id,
                "text": chunk
            }

            if business_id:
                data["business_connection_id"] = business_id

            res = await client.post(f"{TG_API}/sendMessage", json=data)
            print("Telegram send:", res.text)


async def notify_owner(user_name, user_id, text):
    if not OWNER_ID:
        print("OWNER_ID yo'q. Xabar egasiga yuborilmadi.")
        return False

    left_message = clean_left_message(text)

    owner_text = f"""🔔 Bugun sizga ushbu Telegram foydalanuvchisi xabar qoldirdi.

👤 {user_name} ismli kishi
🆔 Telegram ID: {user_id}

💬 Xabari:
{left_message}
"""

    try:
        await send_msg(int(OWNER_ID), owner_text)
        return True
    except Exception as e:
        print("Notify owner error:", e)
        return False


async def ask_ai(text, lang, user_name=None):
    if lang == "ru":
        lang_instruction = "Отвечай только на русском языке."
    elif lang == "en":
        lang_instruction = "Reply only in English."
    else:
        lang_instruction = "Faqat o'zbek tilida javob ber."

    if user_name:
        name_instruction = f"Foydalanuvchining ismi: {user_name}. Kerak bo'lsa ismi bilan murojaat qil."
    else:
        name_instruction = "Foydalanuvchining ismi noma'lum. Ismini qayta-qayta so'rama."

    system_prompt = f"""
Sen NOVA nomli Telegram AI yordamchisan.

Qoidalar:
- {lang_instruction}
- {name_instruction}
- Qisqa, samimiy, muloyim va foydali javob ber.
- O'zingni odam deb ko'rsatma.
- O'zingni NOVA deb tanishtir.
- Agar foydalanuvchi tilni o'zgartirishni so'rasa, keyingi javoblarda o'sha tilda davom et.
- Agar foydalanuvchi xabar qoldirmoqchi bo'lsa, xabari egasiga yetkazilishini ayt.
- Keraksiz uzun javob yozma.
- Suhbat boshida ism so'ralgan bo'lsa, yana qayta so'rama."""

    response = await ai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        temperature=0.7
    )

    answer = response.choices[0].message.content

    if not answer:
        if lang == "ru":
            return "Извините, сейчас не смог ответить."
        if lang == "en":
            return "Sorry, I couldn’t answer right now."
        return "Kechirasiz, hozir javob bera olmadim."

    return answer


@app.on_event("startup")
async def startup():
    webhook = f"{WEBHOOK_URL.rstrip('/')}/webhook"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{TG_API}/setWebhook",
            json={
                "url": webhook,
                "allowed_updates": [
                    "message",
                    "business_message",
                    "business_connection"
                ]
            }
        )
        print("Webhook set:", webhook)
        print("Telegram response:", r.text)


@app.get("/")
async def home():
    return {"status": "Bot ishlayapti"}


async def handle_message(msg, business_id=None, source="Bot chat"):
    if "text" not in msg:
        return

    chat_id = msg["chat"]["id"]
    text = msg["text"].strip()

    user = msg.get("from", {})
    user_id = user.get("id", "unknown")
    first_name = user.get("first_name", "")
    username = user.get("username", "")

    # Business chatda siz o'zingiz yozgan xabarga bot javob bermaydi.
    if source == "Business chat" and OWNER_ID and str(user_id) == str(OWNER_ID):
        print("Owner business message ignored")
        return

    tg_name = first_name or "Noma'lum"
    if username:
        tg_name += f" (@{username})"

    state = get_state(chat_id)

    # /myid faqat oddiy bot chat uchun qulay.
    if text == "/myid":
        await send_msg(chat_id, f"Sizning Telegram ID: {chat_id}", business_id)
        return

    # /reset shu chat xotirasini tozalaydi.
    if text == "/reset":
        CHAT_STATE.pop(chat_id, None)
        await send_msg(chat_id, "Chat sozlamalari tozalandi. Endi qayta yozishingiz mumkin.", business_id)
        return

    # /start tilni majburan o'zbek qilib qo'ymaydi.
    if text == "/start":
        await send_msg(chat_id, start_text(), business_id)
        return

    # Tilni o'zgartirish so'ralgan bo'lsa.
    new_lang = detect_language_change(text)
    if new_lang:
        state["language"] = new_lang
        await send_msg(chat_id, language_changed_text(new_lang), business_id)
        return

    # Birinchi haqiqiy xabardan tilni aniqlaydi.
    if not state.get("language"):
        state["language"] = detect_language(text)

    lang = state["language"]

    # Ismni bir marta aniqlab oladi.
    found_name = extract_name(text)
    if found_name and not state["name"]:
        state["name"] = found_name

    display_name = state["name"] or tg_name

    # Birinchi haqiqiy xabarda o'sha tilda tanishtiradi va ism so'raydi.
    # (Keyingi xabarlarda intro_prefix bo'sh bo'ladi.)
    intro_prefix = ""
    if not state.get("introduced"):
        state["introduced"] = True
        state["asked_name"] = True
        intro_prefix = intro_text(lang) + "\n\n"

    # Agar xabar yetkazib qo'y desa, egasiga yuboradi.
    if wants_to_leave_message(text):
        ok = await notify_owner(display_name, user_id, text)

        if lang == "ru":
            reply = "Хорошо, я передал ваше сообщение." if ok else "Извините, сейчас не смог передать сообщение."
        elif lang == "en":
            reply = "Sure, I’ve forwarded your message." if ok else "Sorry, I couldn’t forward the message right now."
        else:
            reply = "Mayli, xabaringiz yetkazildi." if ok else "Kechirasiz, hozir xabarni yetkaza olmadim."

        await send_msg(chat_id, intro_prefix + reply, business_id)
        return

    # Oddiy AI javob.
    answer = await ask_ai(text, lang, state["name"])
    await send_msg(chat_id, intro_prefix + answer, business_id)


@app.post("/webhook")
async def webhook(request: Request):
    update = await request.json()
    print("UPDATE:", update)

    try:
        if "business_message" in update:
            msg = update["business_message"]
            business_id = msg.get("business_connection_id")
            await handle_message(msg, business_id, "Business chat")

        elif "message" in update:
            msg = update["message"]
            await handle_message(msg, None, "Bot chat")

    except Exception as e:
        print("ERROR:", e)

    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
