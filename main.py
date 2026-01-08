import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from config import config
from database import db
from game_logic import GameManager
from crypto_api import crypto_api
from keyboards import *
from admin_panel import register_admin_handlers, AdminStates

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Инициализация менеджера игр
game_manager = GameManager(bot)

class UserStates(StatesGroup):
    waiting_for_bet = State()
    waiting_for_join = State()

# Обработчики команд
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await db.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name or ""
    )
    
    # Проверяем медиа для главной страницы
    media = await db.get_media('main')
    if media:
        if media['file_type'] == 'photo':
            await message.answer_photo(
                media['file_id'],
                caption=media['caption'] or "🎲 Добро пожаловать в игру в кубики!\n\n"
                                          "Создавайте комнаты, делайте ставки и выигрывайте!",
                reply_markup=main_menu()
            )
        elif media['file_type'] == 'gif':
            await message.answer_animation(
                media['file_id'],
                caption=media['caption'] or "🎲 Добро пожаловать в игру в кубики!\n\n"
                                          "Создавайте комнаты, делайте ставки и выигрывайте!",
                reply_markup=main_menu()
            )
        else:
            await message.answer_video(
                media['file_id'],
                caption=media['caption'] or "🎲 Добро пожаловать в игру в кубики!\n\n"
                                          "Создавайте комнаты, делайте ставки и выигрывайте!",
                reply_markup=main_menu()
            )
    else:
        await message.answer(
            "🎲 Добро пожаловать в игру в кубики!\n\n"
            "Создавайте комнаты, делайте ставки и выигрывайте!",
            reply_markup=main_menu()
        )

@dp.message_handler(lambda m: m.text == "🎲 Создать комнату")
async def create_room_start(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if user and user['is_banned']:
        await message.answer("❌ Вы забанены и не можете создавать комнаты")
        return
    
    media = await db.get_media('create_room')
    if media:
        if media['file_type'] == 'photo':
            await message.answer_photo(
                media['file_id'],
                caption=media['caption'] or "Выберите сумму ставки:",
                reply_markup=bet_keyboard()
            )
        elif media['file_type'] == 'gif':
            await message.answer_animation(
                media['file_id'],
                caption=media['caption'] or "Выберите сумму ставки:",
                reply_markup=bet_keyboard()
            )
        else:
            await message.answer_video(
                media['file_id'],
                caption=media['caption'] or "Выберите сумму ставки:",
                reply_markup=bet_keyboard()
            )
    else:
        await message.answer(
            "Выберите сумму ставки:",
            reply_markup=bet_keyboard()
        )

@dp.callback_query_handler(lambda c: c.data.startswith('bet_'))
async def process_bet(call: types.CallbackQuery):
    bet_amount = float(call.data.split('_')[1])
    
    # Создаем комнату
    success, result, room_id = await game_manager.create_room(call.from_user.id, bet_amount)
    
    if success:
        await call.message.edit_text(
            f"Комната создана!\n"
            f"Ставка: {bet_amount} USD\n\n"
            f"Оплатите ставку по ссылке: {result}\n\n"
            f"После оплаты ожидайте второго игрока."
        )
        
        # Запускаем проверку оплаты
        asyncio.create_task(check_payment_periodically(room_id, call.from_user.id))
    else:
        await call.message.edit_text(f"Ошибка: {result}")

async def check_payment_periodically(room_id: int, user_id: int):
    for _ in range(30):  # Проверяем 30 раз с интервалом 10 секунд
        await asyncio.sleep(10)
        success, message = await game_manager.check_payment(room_id)
        if success:
            await bot.send_message(user_id, message)
            break

@dp.message_handler(lambda m: m.text == "🏠 Активные комнаты")
async def show_rooms(message: types.Message):
    rooms = await db.get_active_rooms()
    
    if not rooms:
        media = await db.get_media('rooms')
        if media:
            if media['file_type'] == 'photo':
                await message.answer_photo(
                    media['file_id'],
                    caption=media['caption'] or "Нет активных комнат"
                )
            elif media['file_type'] == 'gif':
                await message.answer_animation(
                    media['file_id'],
                    caption=media['caption'] or "Нет активных комнат"
                )
            else:
                await message.answer_video(
                    media['file_id'],
                    caption=media['caption'] or "Нет активных комнат"
                )
        else:
            await message.answer("Нет активных комнат")
        return
    
    # Формируем список комнат
    rooms_list = []
    for room in rooms:
        user = await db.get_user(room['creator_id'])
        rooms_list.append({
            'id': room['id'],
            'creator_id': room['creator_id'],
            'creator_username': user['username'] if user else 'Unknown',
            'bet_amount': room['bet_amount'],
            'players_count': 1 + (1 if room['player2_id'] else 0)
        })
    
    await message.answer(
        "Активные комнаты:",
        reply_markup=rooms_keyboard(rooms_list)
    )

@dp.callback_query_handler(lambda c: c.data.startswith('join_'))
async def join_room(call: types.CallbackQuery):
    room_id = int(call.data.split('_')[1])
    
    success, result = await game_manager.join_room(call.from_user.id, room_id)
    
    if success:
        await call.message.edit_text(
            f"Вы присоединились к комнате!\n\n"
            f"Оплатите ставку по ссылке: {result}\n\n"
            f"После оплаты игра начнется автоматически."
        )
        
        # Запускаем проверку оплаты
        asyncio.create_task(check_payment_periodically(room_id, call.from_user.id))
    else:
        await call.message.edit_text(f"Ошибка: {result}")

@dp.message_handler(lambda m: m.text == "💰 Мой баланс")
async def show_balance(message: types.Message):
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("Пользователь не найден")
        return
    
    media = await db.get_media('balance')
    if media:
        caption = media['caption'] or f"💰 Ваш баланс: {user['balance']:.2f} USD"
        if media['file_type'] == 'photo':
            await message.answer_photo(media['file_id'], caption=caption)
        elif media['file_type'] == 'gif':
            await message.answer_animation(media['file_id'], caption=caption)
        else:
            await message.answer_video(media['file_id'], caption=caption)
    else:
        await message.answer(f"💰 Ваш баланс: {user['balance']:.2f} USD")

@dp.message_handler(lambda m: m.text == "📊 Моя статистика")
async def show_stats(message: types.Message):
    user = await db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("Пользователь не найден")
        return
    
    text = f"📊 Ваша статистика:\n\n"
    text += f"👤 Имя: {user['first_name']}\n"
    text += f"📛 Ник: @{user['username']}\n"
    text += f"💰 Баланс: {user['balance']:.2f} USD\n"
    text += f"🏆 Побед: {user['total_wins']}\n"
    text += f"💔 Поражений: {user['total_losses']}\n"
    
    win_rate = (user['total_wins'] / (user['total_wins'] + user['total_losses'])) * 100 if (user['total_wins'] + user['total_losses']) > 0 else 0
    text += f"📈 Процент побед: {win_rate:.1f}%\n"
    text += f"💵 Общая сумма ставок: {user['total_bet']:.2f} USD"
    
    media = await db.get_media('stats')
    if media:
        caption = media['caption'] or text
        if media['file_type'] == 'photo':
            await message.answer_photo(media['file_id'], caption=caption)
        elif media['file_type'] == 'gif':
            await message.answer_animation(media['file_id'], caption=caption)
        else:
            await message.answer_video(media['file_id'], caption=caption)
    else:
        await message.answer(text)

@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def back_to_main(message: types.Message):
    await message.answer("Главное меню:", reply_markup=main_menu())

# Webhook обработчик для CryptoPay
@dp.message_handler(content_types=types.ContentTypes.TEXT)
async def handle_cryptopay_webhook(message: types.Message):
    # Здесь будет обработка вебхуков от CryptoPay
    # В реальном проекте нужно настроить вебхуки
    pass

async def on_startup(dp):
    await db.create_tables()
    logger.info("Бот запущен")

async def on_shutdown(dp):
    logger.info("Бот остановлен")

if __name__ == '__main__':
    from aiogram import executor
    
    # Регистрация админских хэндлеров
    register_admin_handlers(dp)
    
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup,
        on_shutdown=on_shutdown
    )