from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from db.repo import UserRepo

router = Router()

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💣 Мины")],
            [KeyboardButton(text="💰 Баланс")],
        ],
        resize_keyboard=True
    )

@router.message(CommandStart())
async def cmd_start(msg: Message, session: AsyncSession):
    users = UserRepo(session)
    user = await users.get_by_tg(msg.from_user.id)
    if not user:
        user = await users.create(msg.from_user.id, msg.from_user.username)
        await session.commit()

    await msg.answer(
        f"👋 Привет, {msg.from_user.first_name}!\n"
        f"💰 Баланс: <b>{user.balance:,} ⭐</b>\n\n"
        f"Играй: <code>/mines 1000 3</code>\n"
        f"(ставка, количество мин)",
        reply_markup=main_menu()
    )