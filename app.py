import os
import asyncio
import threading
from flask import Flask
from main import bot, dp

# Flask-сервер (Render требует, чтобы сервис слушал порт)
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running"

@app.route('/health')
def health():
    return "OK"


def run_bot():
    """Запускаем бота в отдельном потоке с новым event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(dp.start_polling(bot))


# ✅ Запускаем бота СРАЗУ при импорте (не в __main__!)
threading.Thread(target=run_bot, daemon=True).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
