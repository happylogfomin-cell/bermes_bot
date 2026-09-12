
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


async def main_async():
    threading.Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main_async())
