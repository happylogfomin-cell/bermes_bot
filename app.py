import os
import asyncio
import threading
from flask import Flask
from main import bot, dp

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running"

@app.route('/health')
def health():
    return "OK"


def run_flask():
    """Flask в отдельном потоке — Render требует открытый порт."""
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


async def main_async():
    """Бот в главном потоке — так требует aiogram."""
    # Flask в фоне
    threading.Thread(target=run_flask, daemon=True).start()
    # Бот в главном потоке
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main_async())
