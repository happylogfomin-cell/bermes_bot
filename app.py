import os
import random
import asyncio
import threading
from flask import Flask, send_from_directory, request, jsonify
from aiogram.utils.web_app import safe_parse_webapp_init_data
from main import bot, dp, TOKEN

app = Flask(__name__, static_folder='webapp')


# ====== ВРЕМЕННАЯ БАЗА (в памяти) ======
BALANCES = {}
START_BALANCE = 10000


def get_balance(user_id: int) -> int:
    if user_id not in BALANCES:
        BALANCES[user_id] = START_BALANCE
    return BALANCES[user_id]


def set_balance(user_id: int, value: int):
    BALANCES[user_id] = max(0, value)


# ====== СТАТИКА ======
@app.route('/')
def index():
    return "Bot is running"


@app.route('/health')
def health():
    return "OK"


@app.route('/webapp')
def webapp():
    return send_from_directory('webapp', 'index.html')


@app.route('/webapp/<path:path>')
def webapp_static(path):
    return send_from_directory('webapp', path)


# ====== API: ПОЛУЧИТЬ БАЛАНС ======
@app.route('/api/balance', methods=['POST'])
def api_balance():
    data = request.get_json() or {}
    try:
        parsed = safe_parse_webapp_init_data(token=TOKEN, init_data=data.get('initData', ''))
        user_id = parsed.user.id
    except Exception:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    return jsonify({
        "ok": True,
        "balance": get_balance(user_id),
        "user_id": user_id
    })


# ====== API: КРУТИТЬ СЛОТЫ ======
@app.route('/api/spin', methods=['POST'])
def api_spin():
    data = request.get_json() or {}

    try:
        parsed = safe_parse_webapp_init_data(token=TOKEN, init_data=data.get('initData', ''))
        user_id = parsed.user.id
    except Exception:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    bet = int(data.get('bet', 100))
    balance = get_balance(user_id)

    if balance < bet:
        return jsonify({"ok": False, "error": "Недостаточно средств"})

    balance -= bet

    SYMBOLS = ['🍒', '🍋', '🍇', '💎', '7️⃣']
    reels = [random.choice(SYMBOLS) for _ in range(3)]

    win = 0
    if reels[0] == reels[1] == reels[2] == '7️⃣':
        win = bet * 50
    elif reels[0] == reels[1] == reels[2]:
        win = bet * 10
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        win = bet * 2

    balance += win
    set_balance(user_id, balance)

    return jsonify({
        "ok": True,
        "reels": reels,
        "win": win,
        "bet": bet,
        "balance": balance
    })


# ====== ЗАПУСК ======
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


async def main_async():
    threading.Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main_async())
