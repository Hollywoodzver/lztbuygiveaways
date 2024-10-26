from aiogram import Dispatcher, types, Bot, Router, F
from aiogram.filters import CommandStart, StateFilter, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import aiosqlite
import re
from LOLZTEAM.API import Forum, Market
import config
from config import token, secret, supp
from keyboards import get_admin_keyboard, get_user_keyboard, inline_keyboard, ApplicationActionCallback

market = Market(token=token, language="en")
forum = Forum(token=token, language="en")

class ApplicationForm(StatesGroup):
    profile_link = State()
  

router = Router()

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

@router.message(Command('cleardb'))      
async def clear_db_command(message: types.Message):
     if message.from_user.id in config.ADMIN_IDS:
    # Подключение к базе данных
        async with aiosqlite.connect('bot_database.db') as db:
            await db.execute("DELETE FROM applications")
            await db.execute("DELETE FROM sqlite_sequence WHERE name='applications'")  # Сбрасывает автоинкремент
            await db.commit()
        await message.answer("Database succesfully deleted")

@router.message(F.text == '📑 Получить ссылки на розыгрыши')
async def list_ads_command(message: types.Message):
    if message.from_user.id in config.ADMIN_IDS:
        async with aiosqlite.connect('bot_database.db') as db:
            async with db.execute("SELECT profile_link FROM applications WHERE status = 'approved'") as cursor:
                rows = await cursor.fetchall()
    
        if not rows:
            await message.answer("Нет записей в базе данных.")
            return

        ad_list = "\n".join(f"{i + 1}. {row[0]}" for i, row in enumerate(rows))
        await message.answer(f"Список рекламных объявлений:\n{ad_list}")


is_bot_active = False
@router.message(Command('turnoff'))
async def disabled(message: types.Message):
    if message.from_user.id in config.ADMIN_IDS:
        global is_bot_active
        is_bot_active = False
        await message.answer("Бот выключен!")
    else:
        await message.answer("У вас нет прав для выполнения этой команды!")

@router.message(Command('turnon'))
async def enabled(message: types.Message, command: CommandObject):
    
    if message.from_user.id in config.ADMIN_IDS:
        args1 = command.args
        if not args1:
            await message.reply("Пожалуйста, укажите сумму скупки.")
            return
        if args1.isdigit():
            try:
                config.price_id = args1  # Преобразуем строку аргумента в целое число
                    
            except ValueError:
                await message.reply("ID должен быть числом.")
                return
            await message.answer(f"Бот включен! Цена скупки: {config.price_id}")
            async with aiosqlite.connect('bot_database.db') as db:
                is_bot_active = True
                await db.execute("DELETE FROM applications")
                await db.execute("DELETE FROM sqlite_sequence WHERE name='applications'")  # Сбрасывает автоинкремент
                await db.commit()
                await message.answer("Database succesfully deleted")
    else:
        await message.answer("У вас нет прав для выполнения этой команды!")

@router.message(Command('price'))
async def set_price(message: types.Message, command: CommandObject):
    if message.from_user.id in config.ADMIN_IDS:
        args1 = command.args
        if not args1:
            await message.reply("Пожалуйста, укажите сумму.")
            return
        if args1.isdigit():
            try:
                config.price_id = args1  # Преобразуем строку аргумента в целое число          
            except ValueError:
                await message.reply("ID должен быть числом.")
                return
            await message.answer(config.price_id)
        else:
            await message.reply("ID должен быть числом.")

@router.message(Command('pay'))
async def pay_command(message: types.Message, bot: Bot, command: CommandObject):
    print(f"Initial value of price_id: {config.price_id}")  # Добавьте это для проверки перед использованием
    async with aiosqlite.connect('bot_database.db') as db:
        if message.from_user.id in config.ADMIN_IDS:
            args = command.args

            if not args:
                await message.reply("Пожалуйста, укажите ID строки.")
                return
            if args.isdigit():
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
                                
                                print(f"Using price_id: {config.price_id}")  # Вывод для проверки значения
                                # Здесь проверяем наличие переменной price_id
                                await db.execute('UPDATE applications SET status = "approved" WHERE id = ?', (app_id,))
                                response = market.payments.transfer(
                                    user_id=poster_id, amount=config.price_id, currency="rub", comment=f"Выплата по заявке №{app_id}" ,secret_answer=secret
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


@router.message(Command('info'))
async def get_info(message: types.Message, db):
    if message.from_user.id in config.ADMIN_IDS:
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





@router.message(CommandStart())
async def start_command(message: types.Message):
    user_ids.add(message.from_user.id)  # Добавляем пользователя в список
    if is_bot_active == True:
        if message.from_user.id in config.ADMIN_IDS:
            await message.answer(f"Привет, админ! Текущая цена скупки: {config.price_id} Выберите действие:", reply_markup=get_admin_keyboard())
        else:
  
            await message.answer(f"Привет! Выберите действие:", reply_markup=get_user_keyboard())
    if is_bot_active == False:
        if message.from_user.id in config.ADMIN_IDS:
            await message.answer("!!!!!БОТ ВЫКЛЮЧЕН!!!!! Привет, админ! Выберите действие:", reply_markup=get_admin_keyboard())
        else:
            await message.answer("Скупка приостановлена!")


@router.message(F.text == '📝 Отправить заявку')
async def start_application(message: types.Message, state: FSMContext):
    if is_bot_active == True:
        if await is_blocked(message.from_user.id):
            await message.reply("🚫 Вы заблокированы и не можете отправлять заявки.")
            return

        await message.reply("Отправьте ссылку на розыгрыш:")
        await state.set_state(ApplicationForm.profile_link)
    else:
        await message.reply("Скупка приостановлена!")


@router.message(StateFilter(ApplicationForm.profile_link))
async def process_profile_link(message: types.Message, state: FSMContext, bot: Bot):
    user_data = await state.get_data()

    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute('''INSERT INTO applications (user_id, profile_link) 
                                     VALUES (?, ?)''',
                                  (message.from_user.id, message.text))
        application_id = cursor.lastrowid
        await db.commit()

    admin_message = f"📥 Пришла новая заявка. Заявка ID - {application_id}."
    for admin_id in config.ADMIN_IDS:
        await bot.send_message(admin_id, admin_message)

    await message.reply(f"Telegram ID: {message.from_user.id}, {message.from_user.username}\nID Заявки: {application_id}\nСтатус: ✅ Ваша заявка успешно отправлена!")
    await state.clear()

@router.message(F.text == '📄 Просмотр активных заявок')
async def view_active_applications(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT * FROM applications WHERE status = "pending"') as cursor:
            applications = await cursor.fetchall()
            if not applications:
                await message.reply("Нет активных заявок.")
                return

            for app in applications:
                keyboard_markup = await inline_keyboard()
                await message.answer(
                    f"ID заявки: {app[0]}\nTelegram: {app[2]}\nСтатус: {app[3]}\nTG ID: {app[1]}",
                    reply_markup=keyboard_markup)


@router.message(F.text == '📑 Просмотр закрытых заявок')
async def view_closed_applications(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS:
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

@router.callback_query(ApplicationActionCallback.filter())
async def handle_decision_callback(callback_query: types.CallbackQuery, callback_data: ApplicationActionCallback):
    action, app_id = callback_query.data.split('_')
    action = callback_data.action
    app_id = callback_data.app_id

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
                            amount=config.price_id, 
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
