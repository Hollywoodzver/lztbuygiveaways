from aiogram import Dispatcher, types, Bot
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite
import re
from LOLZTEAM.API import Forum, Market
from config import token, secret, supp

market = Market(token=token, language="en")
forum = Forum(token=token, language="en")

class ApplicationForm(StatesGroup):
    profile_link = State()
    

# Список для хранения идентификаторов пользователей
user_ids = set()
async def init_db():
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            profile_link TEXT,
            status TEXT DEFAULT 'pending'
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS blocked_users (
            user_id INTEGER PRIMARY KEY
        )''')
        await db.commit()

async def is_blocked(user_id):
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT * FROM blocked_users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone() is not None
        
async def clear_db_command(message: types.Message, admin_ids):
     if message.from_user.id in admin_ids:
    # Подключение к базе данных
        async with aiosqlite.connect('bot_database.db') as db:
            await db.execute("DELETE FROM applications")
            await db.execute("DELETE FROM sqlite_sequence WHERE name='applications'")  # Сбрасывает автоинкремент
            await db.commit()
        await message.answer("Database succesfully deleted")

async def list_ads_command(message: types.Message, admin_ids):
    if message.from_user.id in admin_ids:
        async with aiosqlite.connect('bot_database.db') as db:
            async with db.execute("SELECT profile_link FROM applications WHERE status = 'approved'") as cursor:
                rows = await cursor.fetchall()
    
        if not rows:
            await message.answer("Нет записей в базе данных.")
            return

        ad_list = "\n".join(f"{i + 1}. {row[0]}" for i, row in enumerate(rows))
        await message.answer(f"Список рекламных объявлений:\n{ad_list}")


is_bot_active = True
async def disabled(message: types.Message, admin_ids):
    if message.from_user.id in admin_ids:
        global is_bot_active
        is_bot_active = False
        await message.answer("Бот выключен!")
    else:
        await message.answer("У вас нет прав для выполнения этой команды!")


async def enabled(message: types.Message, admin_ids):
    if message.from_user.id in admin_ids:
        global is_bot_active
        global price_id
        if message.from_user.id in admin_ids:
            args1 = message.get_args()
            if not args1:
                await message.reply("Пожалуйста, укажите сумму скупки.")
                return
            try:
                price_id = int(args1)  # Преобразуем строку аргумента в целое число
                
            except ValueError:
                await message.reply("ID должен быть числом.")
                return
            await message.answer(f"Бот включен! Цена скупки: {price_id}")
            async with aiosqlite.connect('bot_database.db') as db:
                is_bot_active = True
                await db.execute("DELETE FROM applications")
                await db.execute("DELETE FROM sqlite_sequence WHERE name='applications'")  # Сбрасывает автоинкремент
                await db.commit()
                await message.answer("Database succesfully deleted")
    else:
        await message.answer("У вас нет прав для выполнения этой команды!")

async def set_price(message: types.Message, admin_ids):
    global price_id
    if message.from_user.id in admin_ids:
        args1 = message.get_args()
        if not args1:
            await message.reply("Пожалуйста, укажите сумму.")
            return
        try:
            price_id = int(args1)  # Преобразуем строку аргумента в целое число
        except ValueError:
            await message.reply("ID должен быть числом.")
            return
        await message.answer(price_id)

async def pay_command(message: types.Message, admin_ids, bot: Bot):
    global price_id
    print(f"Initial value of price_id: {price_id}")  # Добавьте это для проверки перед использованием

    async with aiosqlite.connect('bot_database.db') as db:
        if message.from_user.id in admin_ids:
            args = message.get_args()

            if not args:
                await message.reply("Пожалуйста, укажите ID строки.")
                return

            try:
                app_id = int(args)
            except ValueError:
                await message.reply("ID должен быть числом.")
                return

            async with db.execute('SELECT profile_link FROM applications WHERE id = ?', (app_id,)) as cursor:
                url_row = await cursor.fetchone()
                if url_row:
                    url = url_row[0]
                    print(f"Extracted URL: {url}")  # Отладочный вывод

                    matc = re.search(r'threads/(\d+)', url)
                    if matc:
                        thread_i = matc.group(1)
                        response = forum.posts.list(thread_i)
                        data = response.json()
                        print(f"Forum response data: {data}")  # Отладочный вывод

                        if 'posts' in data and data['posts']:  # Проверяем, что посты есть
                            poster_id = data['posts'][0].get('poster_user_id')
                            profile_link = url
                            
                            print(f"Using price_id: {price_id}")  # Вывод для проверки значения
                            # Здесь проверяем наличие переменной price_id
                            await db.execute('UPDATE applications SET status = "approved" WHERE id = ?', (app_id,))
                            response = market.payments.transfer(
                                user_id=poster_id, amount=price_id, currency="rub", comment=f"Выплата по заявке №{app_id}" ,secret_answer=secret
                            )
                            if response.status_code == 200:  # Если платеж успешен
                                await message.reply(response.json())
                                await message.reply(f"Profile Link: {profile_link}")

                                async with db.execute('SELECT user_id FROM applications WHERE id = ?', (app_id,)) as cursor:
                                    row = await cursor.fetchone()
                                    user_id = row[0]

                                # Отправка сообщения пользователю, который отправил заявку
                                await bot.send_message(user_id, f"Ваш платёж успешно обработан! (ID: {app_id})")
                        else:
                            await message.reply("No posts found in response.")
                    else:
                        await message.reply("Invalid URL format.")
                else:
                    await message.reply("Запись не найдена.")
        await db.commit()


async def get_info(message: types.Message, admin_ids, db):
    if message.from_user.id in admin_ids:
        async with aiosqlite.connect('bot_database.db') as db: 
            args = message.get_args()

            if not args:
                await message.reply("Пожалуйста, укажите ID строки.")
                return

            try:
                app_id = int(args)
            except ValueError:
                await message.reply("ID должен быть числом.")
                return

            async with db.execute('SELECT * FROM applications WHERE id = ?', (app_id,)) as cursor:
                applications = await cursor.fetchall()
                if not applications:
                    await message.reply("Нет активных заявок.")
                    return

                for app in applications:
                    keyboard = InlineKeyboardMarkup()
                    approve_button = InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{app[0]}")
                    reject_button = InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{app[0]}")
                    block_button = InlineKeyboardButton("🚫 Заблокировать", callback_data=f"block_{app[0]}")
                    keyboard.add(approve_button, reject_button, block_button)

                    await message.reply(
                        f"ID заявки: {app[0]}\nTelegram: {app[2]}\nСтатус: {app[3]}\nTG ID: {app[1]}",
                        reply_markup=keyboard)






async def start_command(message: types.Message, admin_ids):
    user_ids.add(message.from_user.id)  # Добавляем пользователя в список
    if is_bot_active == True:
        if message.from_user.id in admin_ids:
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            buttons = ["📄 Просмотр активных заявок", "📑 Просмотр закрытых заявок", "📑 Получить ссылки на розыгрыши"]
            
            keyboard.add(buttons[0], buttons[1])
            keyboard.add(buttons[2])
            await message.reply(f"Привет, админ! Текущая цена скупки: {price_id} Выберите действие:", reply_markup=keyboard)
        else:
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            buttons = ["📝 Отправить заявку"]
            keyboard.add(*buttons)
            await message.reply(f"Привет! Выберите действие:", reply_markup=keyboard)
    if is_bot_active == False:
        if message.from_user.id in admin_ids:
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            buttons = ["📄 Просмотр активных заявок", "📑 Просмотр закрытых заявок"]
            keyboard.add(*buttons)
            await message.reply("!!!!!БОТ ВЫКЛЮЧЕН!!!!! Привет, админ! Выберите действие:", reply_markup=keyboard)
        else:
            await message.reply("Скупка приостановлена!")

async def start_application(message: types.Message):
    if is_bot_active == True:
        if await is_blocked(message.from_user.id):
            await message.reply("🚫 Вы заблокированы и не можете отправлять заявки.")
            return

        await message.reply("Отправьте ссылку на розыгрыш:")
        await ApplicationForm.profile_link.set()
    else:
        await message.reply("Скупка приостановлена!")


async def process_profile_link(message: types.Message, state: FSMContext, bot: Bot, admin_ids):
    user_data = await state.get_data()

    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute('''INSERT INTO applications (user_id, profile_link) 
                                     VALUES (?, ?)''',
                                  (message.from_user.id, message.text))
        application_id = cursor.lastrowid
        await db.commit()

    admin_message = f"📥 Пришла новая заявка. Заявка ID - {application_id}."
    for admin_id in admin_ids:
        await bot.send_message(admin_id, admin_message)

    await message.reply(f"Telegram ID: {message.from_user.id}, {message.from_user.username}\nID Заявки: {application_id}\nСтатус: ✅ Ваша заявка успешно отправлена!")
    await state.finish()


async def view_active_applications(message: types.Message, admin_ids):
    if message.from_user.id not in admin_ids:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT * FROM applications WHERE status = "pending"') as cursor:
            applications = await cursor.fetchall()
            if not applications:
                await message.reply("Нет активных заявок.")
                return

            for app in applications:
                keyboard = InlineKeyboardMarkup()
                approve_button = InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{app[0]}")
                reject_button = InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{app[0]}")
                block_button = InlineKeyboardButton("🚫 Заблокировать", callback_data=f"block_{app[0]}")
                keyboard.add(approve_button, reject_button, block_button)

                await message.reply(
                    f"ID заявки: {app[0]}\nTelegram: {app[2]}\nСтатус: {app[3]}\nTG ID: {app[1]}",
                    reply_markup=keyboard)

async def handle_decision_callback(callback_query: types.CallbackQuery, admin_ids):
    action, app_id = callback_query.data.split('_')
    app_id = int(app_id)
    print('ВСЕ РАБОТАЕТ')

    async with aiosqlite.connect('bot_database.db') as db:
        print(f"Обновляем статус заявки .")
        if action == "approve":
            await db.execute('UPDATE applications SET status = "approved" WHERE id = ?', (app_id,))
            
            await callback_query.message.edit_text(f"Заявка {app_id} одобрена.")
        elif action == "reject":
            await db.execute('UPDATE applications SET status = "rejected" WHERE id = ?', (app_id,))
            await callback_query.message.edit_text(f"Заявка {app_id} отклонена.")
        elif action == "block":
            await db.execute('UPDATE applications SET status = "blocked" WHERE id = ?', (app_id,))
            await db.execute('INSERT INTO blocked_users (user_id) SELECT user_id FROM applications WHERE id = ?', (app_id,))
            await callback_query.message.edit_text(f"Пользователь по заявке {app_id} заблокирован.")
        await db.commit()

async def view_closed_applications(message: types.Message, admin_ids):
    if message.from_user.id not in admin_ids:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT * FROM applications WHERE status IN ("approved", "rejected", "blocked")') as cursor:
            applications = await cursor.fetchall()
            if not applications:
                await message.reply("Нет закрытых заявок.")
                return

            for app in applications:
                await message.reply(f"ID заявки: {app[0]}\nGiveaway Link: {app[2]}\nСтатус: {app[3]}")

async def handle_decision_callback(callback_query: types.CallbackQuery, admin_ids):
    action, app_id = callback_query.data.split('_')
    app_id = int(app_id)

    async with aiosqlite.connect('bot_database.db') as db:
        if action == "approve":
            # Извлечение user_id
            async with db.execute('SELECT user_id FROM applications WHERE id = ?', (app_id,)) as cursor:
                user_id = (await cursor.fetchone())[0]

            # Извлечение profile_link
            async with db.execute('SELECT profile_link FROM applications WHERE id = ?', (app_id,)) as cursor:
                url_row = await cursor.fetchone()
                
                if url_row:  # Проверяем, не пустой ли кортеж
                    url = url_row[0]  # Получаем первое значение из кортежа
                    matc = re.search(r'threads/(\d+)', url)
                    
                    if matc:  # Проверяем, найден ли thread_id
                        thread_id = matc.group(1)
                        
                        # Инициализируем response
                        response = forum.posts.list(thread_id)
                        print(f"Ответ от forum.posts.list: {response}")

                        data = response.json()
                        poster_id = data['posts'][0].get('poster_user_id')
                        profile_link = url

                        # Поиск пользователя на форуме
                        take = forum.users.search(username=f"{profile_link}")
                        print(take)
                        # Выплата
                        response = market.payments.transfer(
                            user_id=poster_id, 
                            amount=price_id, 
                            currency="rub", 
                            comment=f"Выплата по заявке №{app_id}", 
                            secret_answer="15619740"
                        )
                        response_data = response.json()

                        # Проверка на ошибки
                        if 'errors' in response_data:
                            await callback_query.bot.send_message(
                                user_id,
                                text=f"ID Заявки: {app_id}\nОтвет сервера: {response_data['errors']}\nТех. поддержка: {supp}"
                            )
                            await callback_query.message.edit_text(
                                f"При попытке выплаты произошла ошибка:\n{response_data['errors']}"
                            )
                        else:
                            await db.execute('UPDATE applications SET status = "approved" WHERE id = ?', (app_id,))
                            await callback_query.bot.send_message(
                                user_id,
                                text=f"ID Заявки: {app_id}\nСтатус: ✅ Выплачено!"
                            )
                            await callback_query.message.edit_text(f"Заявка {app_id} одобрена.\n{response_data.get('message', 'Выплата прошла успешно.')}")
                    else:
                        await db.execute('UPDATE applications SET status = "rejected" WHERE id = ?', (app_id,))
                        # Логика, если thread_id не найден
                        await callback_query.bot.send_message(
                            callback_query.from_user.id,
                            text="Ошибка: не удалось извлечь thread_id из URL."
                        )
        elif action == "reject":
            await db.execute('UPDATE applications SET status = "rejected" WHERE id = ?', (app_id,))
            async with db.execute('SELECT user_id FROM applications WHERE id = ?', (app_id,)) as cursor:
                user_id = (await cursor.fetchone())[0]

            await callback_query.bot.send_message(
                user_id,
                text=f"ID Заявки: {app_id}\nСтатус: ❌ Отклонено\nКонтакт для обжалования - {supp}."
            )
            await callback_query.message.edit_text(f"Заявка {app_id} отклонена.")
        elif action == "block":
            await db.execute('UPDATE applications SET status = "blocked" WHERE id = ?', (app_id,))
            async with db.execute('SELECT user_id FROM applications WHERE id = ?', (app_id,)) as cursor:
                user_id = (await cursor.fetchone())[0]

            await db.execute('INSERT INTO blocked_users (user_id) VALUES (?)', (user_id,))

            await callback_query.bot.send_message(
                user_id,
                text="🚫 Вы заблокированы."
            )
            await callback_query.message.edit_text(f"Пользователь {user_id} заблокирован.")
        await db.commit()


def register_handlers(dp: Dispatcher, admin_ids):
    dp.register_message_handler(lambda message: pay_command(message, admin_ids, dp.bot), commands="pay", state="*")
    dp.register_message_handler(lambda message: start_command(message, admin_ids), commands="start", state="*")
    dp.register_message_handler(start_application, text="📝 Отправить заявку", state="*")
    dp.register_message_handler(lambda message, state: process_profile_link(message, state, dp.bot, admin_ids), state=ApplicationForm.profile_link)
    dp.register_message_handler(lambda message: view_active_applications(message, admin_ids),
                                text="📄 Просмотр активных заявок")
    dp.register_message_handler(lambda message: view_closed_applications(message, admin_ids),
                                text="📑 Просмотр закрытых заявок")
    dp.register_message_handler(lambda message:  set_price(message, admin_ids), commands="price", state="*")
    dp.register_callback_query_handler(lambda callback_query: handle_decision_callback(callback_query, admin_ids),
                                       lambda c: c.data.startswith(('approve_', 'reject_', 'block_')))
    dp.register_message_handler(lambda message: disabled(message, admin_ids), commands="turnoff", state="*")
    dp.register_message_handler(lambda message: enabled(message, admin_ids), commands="turnon", state="*")
    dp.register_message_handler(lambda message: clear_db_command(message, admin_ids), commands="cleardb", state="*")
    dp.register_message_handler(lambda message: list_ads_command(message, admin_ids),
                                text="📑 Получить ссылки на розыгрыши")
    dp.register_message_handler(lambda message: get_info(message, admin_ids, dp.bot), commands="info", state="*")
