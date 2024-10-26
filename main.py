import logging
import asyncio
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Bot, Dispatcher
from handlers import init_db
import config

from handlers import router


logging.basicConfig(level=logging.INFO)
async def main():
    await init_db()
    bot = Bot(token=config.API_TOKEN)  # Используем API_TOKEN из config.py
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)  

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
