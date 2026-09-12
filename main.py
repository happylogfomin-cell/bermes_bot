import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# ✅ Твой URL с Render
WEBAPP_URL = "https://bermes-bot.onrender.com/webapp"


def get_webapp_keyboard():
    """Кнопка, открывающая Web App прямо в Telegram"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="🎮 Открыть Казино",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )]
        ],
        resize_keyboard=True
    )


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Добро пожаловать в <b>BERM Casino</b> 🎰\n\n"
        f"Нажми кнопку ниже, чтобы начать:",
        reply_markup=get_webapp_keyboard()
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 Команды:\n"
        "/start — открыть казино\n"
        "/help — помощь"
    )


async def main():
    logging.basicConfig(level=logging.INFO)
    print("✅ Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
   
