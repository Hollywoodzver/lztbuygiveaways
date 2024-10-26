from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import KeyboardButton, InlineKeyboardButton
import aiosqlite
from aiogram import types
from aiogram.filters.callback_data import CallbackData

class ApplicationActionCallback(CallbackData, prefix="app_action"):
    action: str
    app_id: int

def get_admin_keyboard():
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text='📄 Просмотр активных заявок'))
    keyboard.add(KeyboardButton(text='📑 Просмотр закрытых заявок'))
    keyboard.add(KeyboardButton(text='📑 Получить ссылки на розыгрыши'))
    return keyboard.as_markup(resize_keyboard=True)

def get_user_keyboard():
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text='📝 Отправить заявку'))
    return keyboard.as_markup(resize_keyboard=True)



# Определяем строго типизированную callback data
class ApplicationActionCallback(CallbackData, prefix="app_action"):
    action: str
    app_id: int

async def inline_keyboard():
    keyboard = InlineKeyboardBuilder()
    
    # Подключение к базе данных
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT * FROM applications WHERE status = "pending"') as cursor:
            applications = await cursor.fetchall()
            for app in applications:
                # Создаем кнопки с использованием строго типизированной callback data
                keyboard.button(
                    text="✅ Одобрить", 
                    callback_data=ApplicationActionCallback(action="approve", app_id=app[0]).pack()
                )
                keyboard.button(
                    text="❌ Отклонить", 
                    callback_data=ApplicationActionCallback(action="reject", app_id=app[0]).pack()
                )
                keyboard.button(
                    text="🚫 Заблокировать", 
                    callback_data=ApplicationActionCallback(action="block", app_id=app[0]).pack()
                )
    return keyboard.as_markup()
