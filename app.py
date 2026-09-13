import os
import asyncio
import secrets
import threading
from datetime import datetime
from flask import Flask, send_from_directory, request, jsonify
from sqlalchemy import select
from aiogram.utils.web_app import safe_parse_webapp_init_data

from main import bot, dp, TOKEN
from db.session import SessionLocal, init_db
from db.models import User

app = Flask(__name__, static_folder='webapp')


# ============ ГЛАВНАЯ ============

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


# ============ API ============

def get_user_from_init(init_data: str):
    """Проверяет initData и возвращает tg_id + username"""
    try:
        parsed = safe_parse_webapp_init_data(token=TOKEN, init_data=init_data)
        return parsed.user.id, parsed.user.username
    except Exception:
        return None, None


async def _get_or_create_user(tg_id: int, username: str | None):
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(tg_id=tg_id, username=username, balance=10000)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user


@app.route('/api/user', methods=['POST'])
def api_user():
    data = request.get_json() or {}
    init = data.get('initData', '')
    tg_id, username = get_user_from_init(init)
    if not tg_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401

    loop = asyncio.new_event_loop()
    user = loop.run_until_complete(_get_or_create_user(tg_id, username))
    loop.close()
    return jsonify({'ok': True, 'balance': user.balance, 'username': user.username or 'Игрок'})


# ============ СЛОТЫ ============

@app.route('/api/spin', methods=['POST'])
def api_spin():
    data = request.get_json() or {}
    init = data.get('initData', '')
    bet = int(data.get('bet', 100))

    tg_id, _ = get_user_from_init(init)
    if not tg_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    if bet < 10:
        return jsonify({'ok': False, 'error': 'min_bet_10'}), 400

    loop = asyncio.new_event_loop()
    user = loop.run_until_complete(_get_or_create_user(tg_id, None))

    if user.balance < bet:
        loop.close()
        return jsonify({'ok': False, 'error': 'no_money', 'balance': user.balance})

    # Крутим 3 барабана: значения 1-7
    reels = [secrets.randbelow(7) + 1 for _ in range(3)]

    # Логика выигрыша
    if reels[0] == reels[1] == reels[2] == 7:
        win = bet * 50   # 777 → x50
        msg = "🎉 ДЖЕКПОТ! Три семёрки!"
    elif reels[0] == reels[1] == reels[2]:
        win = bet * 10   # три одинаковых → x10
        msg = "🔥 Три одинаковых! x10"
    elif 7 in reels:
        win = bet * 3    # есть семёрка → x3
        msg = "✨ Есть семёрка! x3"
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        win = bet * 2    # две одинаковых → x2
        msg = "👍 Две одинаковых! x2"
    else:
        win = 0
        msg = "😢 Повезёт в следующий раз"

    async def _update():
        async with SessionLocal() as session:
            result = await session.execute(select(User).where(User.tg_id == tg_id))
            u = result.scalar_one()
            u.balance = u.balance - bet + win
            await session.commit()
            return u.balance

    new_balance = loop.run_until_complete(_update())
    loop.close()

    return jsonify({
        'ok': True,
        'reels': reels,
        'win': win,
        'bet': bet,
        'balance': new_balance,
        'message': msg
    })


# ============ MINES ============

# Активные игры в памяти: {tg_id: {...}}
ACTIVE_MINES: dict[int, dict] = {}
GRID_SIZE = 5
MINES_COUNT = 3


def _calculate_mines_multiplier(opened: int, mines: int = MINES_COUNT) -> float:
    if opened <= 0:
        return 1.0
    total = GRID_SIZE * GRID_SIZE
    safe = total - mines
    prob = 1.0
    for i in range(opened):
        prob *= (safe - i) / (total - i)
    return round(0.97 / prob, 2)


@app.route('/api/mines/start', methods=['POST'])
def api_mines_start():
    data = request.get_json() or {}
    init = data.get('initData', '')
    bet = int(data.get('bet', 100))

    tg_id, _ = get_user_from_init(init)
    if not tg_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    if bet < 10:
        return jsonify({'ok': False, 'error': 'min_bet_10'}), 400

    loop = asyncio.new_event_loop()
    user = loop.run_until_complete(_get_or_create_user(tg_id, None))

    if user.balance < bet:
        loop.close()
        return jsonify({'ok': False, 'error': 'no_money'})

    # Генерируем поле
    cells = list(range(GRID_SIZE * GRID_SIZE))
    field = set()
    for _ in range(MINES_COUNT):
        field.add(cells.pop(secrets.randbelow(len(cells))))

    ACTIVE_MINES[tg_id] = {
        'bet': bet,
        'field': field,
        'opened': set(),
    }

    async def _deduct():
        async with SessionLocal() as session:
            result = await session.execute(select(User).where(User.tg_id == tg_id))
            u = result.scalar_one()
            u.balance -= bet
            await session.commit()
            return u.balance

    new_balance = loop.run_until_complete(_deduct())
    loop.close()

    return jsonify({'ok': True, 'balance': new_balance, 'size': GRID_SIZE})


@app.route('/api/mines/open', methods=['POST'])
def api_mines_open():
    data = request.get_json() or {}
    init = data.get('initData', '')
    idx = int(data.get('index', -1))

    tg_id, _ = get_user_from_init(init)
    if not tg_id or tg_id not in ACTIVE_MINES:
        return jsonify({'ok': False, 'error': 'no_game'})

    game = ACTIVE_MINES[tg_id]
    if idx in game['opened']:
        return jsonify({'ok': False, 'error': 'already_opened'})

    if idx in game['field']:
        # 💥 Проигрыш
        del ACTIVE_MINES[tg_id]
        return jsonify({
            'ok': True,
            'hit_mine': True,
            'field': list(game['field']),
            'win': 0,
            'balance': None
        })

    game['opened'].add(idx)
    mult = _calculate_mines_multiplier(len(game['opened']))
    potential = int(game['bet'] * mult)

    return jsonify({
        'ok': True,
        'hit_mine': False,
        'opened': list(game['opened']),
        'multiplier': mult,
        'potential_win': potential
    })


@app.route('/api/mines/cashout', methods=['POST'])
def api_mines_cashout():
    data = request.get_json() or {}
    init = data.get('initData', '')

    tg_id, _ = get_user_from_init(init)
    if not tg_id or tg_id not in ACTIVE_MINES:
        return jsonify({'ok': False, 'error': 'no_game'})

    game = ACTIVE_MINES.pop(tg_id)
    opened = len(game['opened'])
    if opened == 0:
        return jsonify({'ok': False, 'error': 'open_at_least_one'})

    mult = _calculate_mines_multiplier(opened)
    win = int(game['bet'] * mult)

    loop = asyncio.new_event_loop()

    async def _add_win():
        async with SessionLocal() as session:
            result = await session.execute(select(User).where(User.tg_id == tg_id))
            u = result.scalar_one()
            u.balance += win
            await session.commit()
            return u.balance

    new_balance = loop.run_until_complete(_add_win())
    loop.close()

    return jsonify({'ok': True, 'win': win, 'balance': new_balance, 'multiplier': mult})


# ============ ЗАПУСК ============

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


async def main_async():
    await init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main_async())
