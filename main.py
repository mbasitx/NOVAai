import os
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

SYSTEM = """
Sen NOVA nomli Telegram AI yordamchisan.

Qoidalar:
- Foydalanuvchi qaysi tilda yozsa, o‘sha tilda javob ber.
- Agar English yozsa, English javob ber.
- Kim seni yaratgan deb yozsa Meni drbasitx yasalgan deb yoz yoki boshqa tilda sorasa ham shuni tarjima qilib yoz.
- Agar Russian/Ruscha yozsa, Russian javob ber.
- Agar Uzbek/O‘zbekcha yozsa, Uzbek javob ber, istagan tilida javob yoz.
- Agar foydalanuvchi suhbat o‘rtasida boshqa tilni so‘rasa, o‘sha tilga o‘t.
- O‘zingni tanishtirganda foydalanuvchi tilida tanishtir:
  Uzbek: Salom, NOVA man. Qanday yordam bera olaman?
  English: Hi, I’m NOVA. How can I help?
  Russian: Здравствуйте, я NOVA. Чем могу помочь?
- Suhbat boshida bir marta ismini so‘ra.
- Agar ismini aytmasa, qayta-qayta so‘rama.
- Qisqa, muloyim va foydali javob ber.
"""

async def ask_ai(text):
    r = await ai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text}
        ]
    )
    return r.choices[0].message.content or "Kechirasiz, javob bera olmadim."

async def send_msg(chat_id, text, business_id=None):
    data = {
        "chat_id": chat_id,
        "text": text[:4096]
    }

    if business_id:
        data["business_connection_id"] = business_id

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(f"{TG_API}/sendMessage", json=data)
        print("Telegram:", res.text)
def need_forward(text):
    t = text.lower()
    return any(x in t for x in [
        "xabar yetkaz",
        "yetkazib qo'y",
        "yetkazib qoy",
        "xabar qoldir",
        "adminga ayt",
        "egasiga ayt",
        "tell admin",
        "tell owner",
        "leave a message",
        "передай",
        "сообщи"
    ])


async def notify_owner(user_name, user_id, text):
    if not OWNER_ID:
        print("OWNER_ID yo'q")
        return

    msg = f"""🔔 Bugun sizga ushbu Telegram foydalanuvchisi xabar qoldirdi.

👤 Ismi: {user_name}
🆔 Telegram ID: {user_id}

💬 Xabari:
{text}
"""


if need_forward(text):
    await notify_owner(user_name, user_id, text)
user = msg.get("from", {})
user_id = user.get("id", "unknown")
user_name = user.get("first_name", "Noma'lum")
    # Agar Business chatda xabarni o'zingiz yozgan bo'lsangiz, bot javob bermaydi
    if source == "Business chat" and OWNER_ID and str(user_id) == str(OWNER_ID):
        print("Owner message ignored")
        return
if user.get("username"):
    user_name += f" (@{user.get('username')})"
answer = await ask_ai(text)
await send_msg(chat_id, answer, business_id)
    await send_message(int(OWNER_ID), message)
@app.on_event("startup")
async def startup():
    webhook = f"{WEBHOOK_URL}/webhook"

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

@app.post("/webhook")
async def webhook(request: Request):
    update = await request.json()
    print("UPDATE:", update)

    try:
        if "business_message" in update:
            msg = update["business_message"]

            if "text" not in msg:
                return {"ok": True}

            chat_id = msg["chat"]["id"]
            text = msg["text"]
            business_id = msg.get("business_connection_id")

            answer = await ask_ai(text)
            await send_msg(chat_id, answer, business_id)

        elif "message" in update:
            msg = update["message"]

            if "text" not in msg:
                return {"ok": True}

            chat_id = msg["chat"]["id"]
            text = msg["text"]

            if text == "/start":
                await send_msg(chat_id, "Salom! Men NOVA xabar yozing:")
            else:
    user = msg.get("from", {})
    user_id = user.get("id", "unknown")
    user_name = user.get("first_name", "Noma'lum")

    if user.get("username"):
        user_name += f" (@{user.get('username')})"

    if need_forward(text):
        await notify_owner(user_name, user_id, text)

    answer = await ask_ai(text)
    await send_msg(chat_id, answer)

    except Exception as e:
        print("ERROR:", e)

    return {"ok": True}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
