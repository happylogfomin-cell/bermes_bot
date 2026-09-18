import os
import asyncio
import secrets
import threading
import time
from flask import Flask, send_from_directory, request, jsonify
from sqlalchemy import select
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiogram.types import LabeledPrice

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


# ============ HELPERS ============

def get_user_from_init(init_data: str):
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

    reels = [secrets.randbelow(7) + 1 for _ in range(3)]

    if reels[0] == reels[1] == reels[2] == 7:
        win = bet * 50
        msg = "🎉 ДЖЕКПОТ! Три семёрки!"
    elif reels[0] == reels[1] == reels[2]:
        win = bet * 10
        msg = "🔥 Три одинаковых! x10"
    elif 7 in reels:
        win = bet * 3
        msg = "✨ Есть семёрка! x3"
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        win = bet * 2
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


# ============ МИНЫ ============

ACTIVE_MINES = {}
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

    cells = list(range(GRID_SIZE * GRID_SIZE))
    field = set()
    for _ in range(MINES_COUNT):
        field.add(cells.pop(secrets.randbelow(len(cells))))

    ACTIVE_MINES[tg_id] = {'bet': bet, 'field': field, 'opened': set()}

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
        del ACTIVE_MINES[tg_id]
        return jsonify({'ok': True, 'hit_mine': True, 'field': list(game['field'])})

    game['opened'].add(idx)
    mult = _calculate_mines_multiplier(len(game['opened']))
    return jsonify({
        'ok': True,
        'hit_mine': False,
        'opened': list(game['opened']),
        'multiplier': mult,
        'potential_win': int(game['bet'] * mult)
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
    # ============ CRASH (РАКЕТКА) ============

def generate_crash_point() -> float:
    r = secrets.randbelow(1000) / 1000.0
    if r < 0.5:
        return round(1.0 + r * 2, 2)
    elif r < 0.8:
        return round(2.0 + (r - 0.5) * 10, 2)
    elif r < 0.95:
        return round(5.0 + (r - 0.8) * 33, 2)
    else:
        return round(10.0 + (r - 0.95) * 1800, 2)


ACTIVE_CRASH = {}


@app.route('/api/crash/start', methods=['POST'])
def api_crash_start():
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

    ACTIVE_CRASH[tg_id] = {
        'bet': bet,
        'crash_point': generate_crash_point(),
        'start_time': time.time()
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
    return jsonify({'ok': True, 'balance': new_balance})


@app.route('/api/crash/status', methods=['POST'])
def api_crash_status():
    data = request.get_json() or {}
    init = data.get('initData', '')

    tg_id, _ = get_user_from_init(init)
    if not tg_id or tg_id not in ACTIVE_CRASH:
        return jsonify({'ok': False, 'error': 'no_game'})

    game = ACTIVE_CRASH[tg_id]
    elapsed = time.time() - game['start_time']
    current_mult = round(1.0 + elapsed * 0.5, 2)

    if current_mult >= game['crash_point']:
        del ACTIVE_CRASH[tg_id]
        return jsonify({
            'ok': True, 'crashed': True,
            'crash_point': game['crash_point'],
            'multiplier': game['crash_point'], 'win': 0
        })

    return jsonify({
        'ok': True, 'crashed': False,
        'multiplier': current_mult,
        'potential_win': int(game['bet'] * current_mult)
    })


@app.route('/api/crash/cashout', methods=['POST'])
def api_crash_cashout():
    data = request.get_json() or {}
    init = data.get('initData', '')

    tg_id, _ = get_user_from_init(init)
    if not tg_id or tg_id not in ACTIVE_CRASH:
        return jsonify({'ok': False, 'error': 'no_game'})

    game = ACTIVE_CRASH.pop(tg_id)
    elapsed = time.time() - game['start_time']
    current_mult = round(1.0 + elapsed * 0.5, 2)

    if current_mult >= game['crash_point']:
        return jsonify({'ok': False, 'error': 'already_crashed'})

    win = int(game['bet'] * current_mult)
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
    return jsonify({'ok': True, 'win': win, 'multiplier': current_mult, 'balance': new_balance})


# ============ STARS PAYMENT ============

@app.route('/api/stars/invoice', methods=['POST'])
def api_stars_invoice():
    data = request.get_json() or {}
    init = data.get('initData', '')
    stars = int(data.get('stars', 100))

    tg_id, _ = get_user_from_init(init)
    if not tg_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401

    async def _create():
        return await bot.create_invoice_link(
            title="Пополнение баланса BERM",
            description=f"{stars} ⭐ на баланс",
            payload=f"stars_{tg_id}_{stars}",
            currency="XTR",
            prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)]
        )

    loop = asyncio.new_event_loop()
    try:
        link = loop.run_until_complete(_create())
        return jsonify({'ok': True, 'link': link})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        loop.close()


# ============ CRYPTO PAY ============

from aiocryptopay import AioCryptoPay, Networks

CRYPTO_TOKEN = os.getenv("CRYPTO_PAY_TOKEN", "")


@app.route('/api/crypto/invoice', methods=['POST'])
def api_crypto_invoice():
    data = request.get_json() or {}
    init = data.get('initData', '')
    amount = float(data.get('amount', 1))

    tg_id, _ = get_user_from_init(init)
    if not tg_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401

    if not CRYPTO_TOKEN:
        return jsonify({'ok': False, 'error': 'crypto_not_configured'}), 500

    async def _create():
        crypto = AioCryptoPay(token=CRYPTO_TOKEN, network=Networks.MAIN_NET)
        try:
            invoice = await crypto.create_invoice(
                asset='USDT', amount=amount,
                description="Пополнение BERM Casino",
                payload=f"crypto_{tg_id}",
                expires_in=600
            )
            return invoice.bot_invoice_url
        finally:
            await crypto.close()

    loop = asyncio.new_event_loop()
    try:
        url = loop.run_until_complete(_create())
        return jsonify({'ok': True, 'link': url})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        loop.close()


@app.route('/crypto/webhook/<secret>', methods=['POST'])
def crypto_webhook(secret):
    if secret != "berm_2026_secret":
        return "Forbidden", 403

    data = request.json or {}

    if data.get('update_type') == 'invoice_paid':
        payload = data.get('payload', {})
        tg_id_raw = payload.get('payload', '')
        amount_usdt = float(payload.get('amount', 0))

        try:
            tg_id = int(tg_id_raw.split('_')[1])
        except:
            tg_id = 0

        if tg_id and amount_usdt > 0:
            coins = int(amount_usdt * 1000)

            async def _add():
                async with SessionLocal() as session:
                    result = await session.execute(select(User).where(User.tg_id == tg_id))
                    user = result.scalar_one_or_none()
                    if user:
                        user.balance += coins
                        await session.commit()

            loop = asyncio.new_event_loop()
            loop.run_until_complete(_add())
            loop.close()

    return "OK", 200


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
