import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Создаём бота и диспетчер
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(f"Привет, {message.from_user.first_name}! Я бот Garila. 🎮")

# Обработчик команды /help
@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer("Доступные команды:\n/start - Начать\n/help - Помощь")

# Эхо-бот (отвечает на любой текст) — убери, если не нужно
@dp.message()
async def echo_handler(message: Message):
    await message.answer(f"Ты написал: {message.text}")

async def main():
    logging.basicConfig(level=logging.INFO)
    print("✅ Бот Garila запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())