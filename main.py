import os
import httpx
import uvicorn
from fastapi import FastAPI, Request
from openai import AsyncOpenAI

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN yo'q")
if not OPENAI_KEY:
    raise RuntimeError("OPENAI_API_KEY yo'q")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL yo'q")

app = FastAPI()
ai = AsyncOpenAI(api_key=OPENAI_KEY)
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

SYSTEM = "Sen Telegram uchun AI yordamchisan. Qisqa, muloyim va foydali javob ber. Asosan o'zbek tilida yoz."

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
        print(res.text)

@app.on_event("startup")
async def startup():
    webhook = f"{WEBHOOK_URL}/webhook"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{TG_API}/setWebhook",
            json={
                "url": webhook,
                "allowed_updates": ["message", "business_message", "business_connection"]
            }
        )
        print("Webhook:", r.text)

@app.get("/")
async def home():
    return {"status": "Bot ishlayapti"}

@app.post("/webhook")
async def webhook(request: Request):
    update = await request.json()
    print(update)

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
                await send_msg(chat_id, "Salom! Men NOVA man xabar yozib qoldiring:")
            else:
                answer = await ask_ai(text)
                await send_msg(chat_id, answer)

    except Exception as e:
        print("ERROR:", e)

    return {"ok": True}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
