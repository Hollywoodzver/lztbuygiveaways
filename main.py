import logging
from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from handlers import  init_db, register_handlers
from config import API_TOKEN, ADMIN_IDS

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

async def on_startup(dp):
    await init_db()

register_handlers(dp, ADMIN_IDS)
print('000000')
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)