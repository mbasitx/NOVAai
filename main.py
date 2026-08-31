import os
import httpx
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from openai import AsyncOpenAI
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Client("my_secretary_bot", api_id=API_ID, api_hash=API_HASH)

@app.on_message(filters.private & ~filters.me)
def secretary_handler(client, message):
    user_text = message.text
    if not user_text:
        return

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Sen egasining shaxsiy sekretarisan. Uning nomidan qisqa va aniq javob yoz."},
            {"role": "user", "content": user_text}
        ]
    )

    ai_reply = response.choices[0].message.content
    message.reply_text(ai_reply)

app.run()
