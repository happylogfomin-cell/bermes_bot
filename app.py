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
