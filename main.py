import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    PreCheckoutQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from dotenv import load_dotenv
from sqlalchemy import select

from db.session import init_db, SessionLocal
from db.models import User

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

WEBAPP_URL = "https://bermes-bot.onrender.com/webapp"
CHAT_URL = "https://t.me/"
CHANNEL_URL = "https://t.me/"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


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


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await _get_or_create_user(message.from_user.id, message.from_user.username)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=WEBAPP_URL))],
            [
                InlineKeyboardButton(text="Чат", url=CHAT_URL),
                InlineKeyboardButton(text="Канал", url=CHANNEL_URL),
            ],
        ]
    )

    await message.answer(
        "🎁 <b>Выиграйте NFT-подарки мечты!</b>\n\n"
        "Вам доступен бесплатный кейс, а также рулетка, краш, PvP, "
        "слоты, яйца и апгрейд.",
        reply_markup=kb,
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>Команды:</b>\n"
        "/start — открыть казино\n"
        "/help — помощь"
    )


# ============ STARS PAYMENT ============

@dp.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@dp.message(lambda m: m.successful_payment is not None)
async def on_successful_payment(message: Message):
    payment = message.successful_payment
    tg_id = message.from_user.id
    payload = payment.invoice_payload or ""

    stars = 0
    try:
        parts = payload.split("_")
        if len(parts) >= 3 and parts[0] == "stars":
            stars = int(parts[2])
    except Exception:
        stars = 0

    if stars <= 0:
        await message.answer("❌ Ошибка обработки платежа")
        return

    coins = stars * 100

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(tg_id=tg_id, username=message.from_user.username, balance=10000 + coins)
            session.add(user)
        else:
            user.balance += coins
        await session.commit()
        new_balance = user.balance

    await message.answer(
        f"✅ <b>Оплата прошла!</b>\n"
        f"⭐ Получено: <b>{stars}</b> звёзд\n"
        f"💰 Начислено: <b>+{coins:,} $</b>\n"
        f"💳 Баланс: <b>{new_balance:,} $</b>"
    )


# ============ ЗАПУСК ============

async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    print("✅ Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
