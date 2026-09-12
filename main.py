import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from db.session import init_db, SessionLocal
from bot.handlers import start, mines

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


async def db_middleware(handler, event, data):
    async with SessionLocal() as session:
        data["session"] = session
        return await handler(event, data)


async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()

    dp.update.middleware(db_middleware)
    dp.include_router(start.router)
    dp.include_router(mines.router)

    print("✅ Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())