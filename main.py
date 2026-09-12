import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(f"Привет, {message.from_user.first_name}! Я бот Garila. 🎮")


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("Команды: /start, /help")


async def main():
    logging.basicConfig(level=logging.INFO)
    print("✅ Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
