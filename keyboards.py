from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("🎲 Создать комнату"))
    keyboard.add(KeyboardButton("🏠 Активные комнаты"))
    keyboard.add(KeyboardButton("💰 Мой баланс"))
    keyboard.add(KeyboardButton("📊 Моя статистика"))
    return keyboard

def admin_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("📊 Статистика бота"))
    keyboard.add(KeyboardButton("👥 Управление пользователями"))
    keyboard.add(KeyboardButton("🖼 Управление медиа"))
    keyboard.add(KeyboardButton("💰 Пополнение баланса"))
    keyboard.add(KeyboardButton("⬅️ Назад"))
    return keyboard

def bet_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=3)
    bets = [1, 2, 5, 10, 20, 50, 100]
    row = []
    for bet in bets:
        row.append(InlineKeyboardButton(f"{bet} USD", callback_data=f"bet_{bet}"))
        if len(row) == 3:
            keyboard.row(*row)
            row = []
    if row:
        keyboard.row(*row)
    return keyboard

def rooms_keyboard(rooms):
    keyboard = InlineKeyboardMarkup(row_width=1)
    for room in rooms:
        player1 = f"@{room['creator_username']}" if room.get('creator_username') else f"ID: {room['creator_id']}"
        btn_text = f"{player1} | {room['bet_amount']} USD | {room['players_count']}/2"
        keyboard.add(InlineKeyboardButton(btn_text, callback_data=f"join_{room['id']}"))
    return keyboard

def user_management_keyboard(username, is_banned):
    keyboard = InlineKeyboardMarkup(row_width=2)
    if is_banned:
        keyboard.add(InlineKeyboardButton("✅ Разбанить", callback_data=f"unban_{username}"))
    else:
        keyboard.add(InlineKeyboardButton("❌ Забанить", callback_data=f"ban_{username}"))
    keyboard.add(InlineKeyboardButton("📊 Статистика", callback_data=f"stats_{username}"))
    return keyboard

def media_sections_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    sections = [
        ("main", "Главная"),
        ("create_room", "Создание комнаты"),
        ("rooms", "Список комнат"),
        ("balance", "Баланс"),
        ("stats", "Статистика"),
        ("win", "Победа"),
        ("lose", "Проигрыш")
    ]
    row = []
    for section, title in sections:
        row.append(InlineKeyboardButton(title, callback_data=f"media_{section}"))
        if len(row) == 2:
            keyboard.row(*row)
            row = []
    if row:
        keyboard.row(*row)
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
    return keyboard

def cancel_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return keyboard