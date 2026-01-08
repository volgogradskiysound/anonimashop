from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InputFile
from config import config
from database import db
from keyboards import *

class AdminStates(StatesGroup):
    waiting_for_media = State()
    waiting_for_media_caption = State()
    waiting_for_deposit = State()
    waiting_for_deposit_amount = State()

async def admin_start(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    
    await message.answer(
        "👨‍💻 Панель администратора",
        reply_markup=admin_menu()
    )

async def admin_stats(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    
    stats = await db.get_bot_stats()
    
    text = "📊 *Статистика бота*\n\n"
    text += f"👥 Всего пользователей: {stats['total_users']}\n"
    text += f"🎮 Всего игр: {stats['total_games']}\n"
    text += f"💰 Общая сумма ставок: {stats['total_bets']:.2f} USD\n"
    text += f"🏦 Доход проекта: {stats['project_income']:.2f} USD\n"
    text += f"📈 Пополнений: {stats['total_deposits']:.2f} USD\n"
    text += f"📉 Выводов: {stats['total_withdrawals']:.2f} USD\n"
    
    await message.answer(text, parse_mode='Markdown')

async def admin_user_management(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔍 Найти пользователя по @username", callback_data="find_user"))
    await message.answer("Управление пользователями:", reply_markup=keyboard)

async def find_user_by_username(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите @username пользователя (без @):")
    await state.set_state("waiting_for_username")

async def process_username(message: types.Message, state: FSMContext):
    username = message.text.strip()
    
    # Ищем пользователя в базе
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = await cursor.fetchone()
    
    if user:
        user_dict = dict(user)
        
        # Пытаемся получить фото пользователя
        try:
            user_profile = await message.bot.get_user_profile_photos(user_dict['user_id'])
            if user_profile.total_count > 0:
                photo = user_profile.photos[0][-1]
                await message.bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo.file_id,
                    caption=f"👤 Пользователь: @{username}\n"
                           f"🆔 ID: {user_dict['user_id']}\n"
                           f"💰 Баланс: {user_dict['balance']:.2f} USD\n"
                           f"🏆 Побед: {user_dict['total_wins']}\n"
                           f"💔 Поражений: {user_dict['total_losses']}\n"
                           f"🚫 Статус: {'Забанен' if user_dict['is_banned'] else 'Активен'}",
                    reply_markup=user_management_keyboard(username, user_dict['is_banned'])
                )
            else:
                await message.answer(
                    f"👤 Пользователь: @{username}\n"
                    f"🆔 ID: {user_dict['user_id']}\n"
                    f"💰 Баланс: {user_dict['balance']:.2f} USD\n"
                    f"🏆 Побед: {user_dict['total_wins']}\n"
                    f"💔 Поражений: {user_dict['total_losses']}\n"
                    f"🚫 Статус: {'Забанен' if user_dict['is_banned'] else 'Активен'}",
                    reply_markup=user_management_keyboard(username, user_dict['is_banned'])
                )
        except:
            await message.answer(
                f"👤 Пользователь: @{username}\n"
                f"🆔 ID: {user_dict['user_id']}\n"
                f"💰 Баланс: {user_dict['balance']:.2f} USD\n"
                f"🏆 Побед: {user_dict['total_wins']}\n"
                f"💔 Поражений: {user_dict['total_losses']}\n"
                f"🚫 Статус: {'Забанен' if user_dict['is_banned'] else 'Активен'}",
                reply_markup=user_management_keyboard(username, user_dict['is_banned'])
            )
    else:
        await message.answer("Пользователь не найден")
    
    await state.finish()

async def ban_unban_user(call: types.CallbackQuery):
    data = call.data.split('_')
    action = data[0]
    username = data[1]
    
    if action == 'ban':
        await db.ban_user(username, True)
        await call.message.edit_caption(
            caption=f"✅ Пользователь @{username} забанен",
            reply_markup=user_management_keyboard(username, True)
        )
    elif action == 'unban':
        await db.ban_user(username, False)
        await call.message.edit_caption(
            caption=f"✅ Пользователь @{username} разбанен",
            reply_markup=user_management_keyboard(username, False)
        )

async def admin_media_management(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    
    await message.answer(
        "Выберите раздел для добавления медиа:",
        reply_markup=media_sections_keyboard()
    )

async def select_media_section(call: types.CallbackQuery, state: FSMContext):
    section = call.data.split('_')[1]
    
    await state.update_data(section=section)
    await AdminStates.waiting_for_media.set()
    
    await call.message.edit_text(
        f"Отправьте фото, GIF или видео для раздела '{section}':",
        reply_markup=cancel_keyboard()
    )

async def process_media(message: types.Message, state: FSMContext):
    data = await state.get_data()
    section = data.get('section')
    
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = 'photo'
    elif message.video:
        file_id = message.video.file_id
        file_type = 'video'
    elif message.animation:
        file_id = message.animation.file_id
        file_type = 'gif'
    else:
        await message.answer("Пожалуйста, отправьте фото, GIF или видео")
        return
    
    await state.update_data(file_id=file_id, file_type=file_type)
    await AdminStates.waiting_for_media_caption.set()
    
    await message.answer(
        "Отправьте подпись для медиа (или отправьте '-' если подпись не нужна):",
        reply_markup=cancel_keyboard()
    )

async def process_media_caption(message: types.Message, state: FSMContext):
    data = await state.get_data()
    section = data.get('section')
    file_id = data.get('file_id')
    file_type = data.get('file_type')
    caption = message.text if message.text != '-' else ""
    
    await db.add_media(section, file_type, file_id, caption)
    
    await message.answer(f"✅ Медиа добавлено в раздел '{section}'")
    await state.finish()
    await admin_media_management(message)

async def admin_deposit(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    
    await AdminStates.waiting_for_deposit.set()
    await message.answer(
        "Введите @username пользователя для пополнения баланса (без @):",
        reply_markup=cancel_keyboard()
    )

async def process_deposit_username(message: types.Message, state: FSMContext):
    username = message.text.strip()
    
    # Проверяем существование пользователя
    user = await db.get_user_by_username(username)
    if not user:
        await message.answer("Пользователь не найден")
        return
    
    await state.update_data(username=username, user_id=user['user_id'])
    await AdminStates.waiting_for_deposit_amount.set()
    
    await message.answer("Введите сумму для пополнения (в USD):")

async def process_deposit_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        
        data = await state.get_data()
        user_id = data.get('user_id')
        username = data.get('username')
        
        # Пополняем баланс
        await db.update_user_balance(user_id, amount)
        await db.add_transaction(user_id, amount, 'deposit', description='Пополнение администратором')
        
        await message.answer(f"✅ Баланс пользователя @{username} пополнен на {amount} USD")
        
        # Уведомляем пользователя
        await message.bot.send_message(
            user_id,
            f"💰 Ваш баланс пополнен администратором на {amount} USD"
        )
        
    except ValueError:
        await message.answer("Пожалуйста, введите корректную сумму")
        return
    
    await state.finish()

async def cancel_action(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.edit_text("Действие отменено")

def register_admin_handlers(dp: Dispatcher):
    dp.register_message_handler(admin_start, commands=["admin"])
    dp.register_message_handler(admin_stats, lambda m: m.text == "📊 Статистика бота")
    dp.register_message_handler(admin_user_management, lambda m: m.text == "👥 Управление пользователями")
    dp.register_message_handler(admin_media_management, lambda m: m.text == "🖼 Управление медиа")
    dp.register_message_handler(admin_deposit, lambda m: m.text == "💰 Пополнение баланса")
    
    dp.register_callback_query_handler(find_user_by_username, lambda c: c.data == "find_user")
    dp.register_message_handler(process_username, state="waiting_for_username")
    dp.register_callback_query_handler(ban_unban_user, lambda c: c.data.startswith(('ban_', 'unban_')))
    
    dp.register_callback_query_handler(select_media_section, lambda c: c.data.startswith('media_'))
    dp.register_message_handler(process_media, content_types=['photo', 'video', 'animation'], state=AdminStates.waiting_for_media)
    dp.register_message_handler(process_media_caption, state=AdminStates.waiting_for_media_caption)
    
    dp.register_message_handler(process_deposit_username, state=AdminStates.waiting_for_deposit)
    dp.register_message_handler(process_deposit_amount, state=AdminStates.waiting_for_deposit_amount)
    
    dp.register_callback_query_handler(cancel_action, lambda c: c.data == "cancel", state="*")