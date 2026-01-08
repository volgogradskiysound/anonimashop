import aiosqlite
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from config import config

class Database:
    def __init__(self):
        self.db_path = config.DB_PATH
    
    async def create_tables(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Пользователи
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance REAL DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    total_losses INTEGER DEFAULT 0,
                    total_bet REAL DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Комнаты
            await db.execute('''
                CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creator_id INTEGER,
                    player1_id INTEGER,
                    player2_id INTEGER,
                    bet_amount REAL,
                    status TEXT DEFAULT 'waiting', -- waiting, playing, finished
                    player1_paid INTEGER DEFAULT 0,
                    player2_paid INTEGER DEFAULT 0,
                    player1_dice INTEGER,
                    player2_dice INTEGER,
                    winner_id INTEGER,
                    prize_amount REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP
                )
            ''')
            
            # Транзакции
            await db.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    type TEXT, -- deposit, withdraw, win, loss
                    room_id INTEGER,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Статистика
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bot_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE,
                    total_users INTEGER DEFAULT 0,
                    total_games INTEGER DEFAULT 0,
                    total_bets REAL DEFAULT 0,
                    project_income REAL DEFAULT 0,
                    deposits REAL DEFAULT 0,
                    withdrawals REAL DEFAULT 0
                )
            ''')
            
            # Медиа
            await db.execute('''
                CREATE TABLE IF NOT EXISTS media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    section TEXT,
                    file_type TEXT, -- photo, gif, video
                    file_id TEXT,
                    caption TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await db.commit()
    
    # Методы для работы с пользователями
    async def add_user(self, user_id: int, username: str, first_name: str, last_name: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name))
            await db.commit()
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_user_balance(self, user_id: int, amount: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
            await db.commit()
    
    async def ban_user(self, username: str, ban: bool = True):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET is_banned = ? WHERE username = ?', (1 if ban else 0, username))
            await db.commit()
    
    # Методы для комнат
    async def create_room(self, creator_id: int, bet_amount: float) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO rooms (creator_id, player1_id, bet_amount, status)
                VALUES (?, ?, ?, 'waiting')
            ''', (creator_id, creator_id, bet_amount))
            await db.commit()
            return cursor.lastrowid
    
    async def get_room(self, room_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM rooms WHERE id = ?', (room_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_room(self, room_id: int, **kwargs):
        async with aiosqlite.connect(self.db_path) as db:
            set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values())
            values.append(room_id)
            await db.execute(f'UPDATE rooms SET {set_clause} WHERE id = ?', values)
            await db.commit()
    
    async def get_active_rooms(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM rooms WHERE status = "waiting" ORDER BY created_at DESC')
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # Методы для транзакций
    async def add_transaction(self, user_id: int, amount: float, trans_type: str, room_id: int = None, description: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO transactions (user_id, amount, type, room_id, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, amount, trans_type, room_id, description))
            await db.commit()
    
    # Методы для статистики
    async def get_bot_stats(self) -> Dict:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Общая статистика
            cursor = await db.execute('SELECT COUNT(*) as total_users FROM users')
            total_users = (await cursor.fetchone())['total_users']
            
            cursor = await db.execute('SELECT COUNT(*) as total_games FROM rooms WHERE status = "finished"')
            total_games = (await cursor.fetchone())['total_games']
            
            cursor = await db.execute('SELECT SUM(bet_amount) as total_bets FROM rooms WHERE status = "finished"')
            total_bets_row = await cursor.fetchone()
            total_bets = total_bets_row['total_bets'] or 0
            
            cursor = await db.execute('SELECT SUM(amount) as project_income FROM transactions WHERE type = "project_fee"')
            project_income_row = await cursor.fetchone()
            project_income = project_income_row['project_income'] or 0
            
            cursor = await db.execute('SELECT SUM(amount) as total_deposits FROM transactions WHERE type = "deposit"')
            deposits_row = await cursor.fetchone()
            total_deposits = deposits_row['total_deposits'] or 0
            
            cursor = await db.execute('SELECT SUM(amount) as total_withdrawals FROM transactions WHERE type = "withdraw"')
            withdrawals_row = await cursor.fetchone()
            total_withdrawals = withdrawals_row['total_withdrawals'] or 0
            
            # Сегодняшняя статистика
            today = datetime.now().strftime('%Y-%m-%d')
            cursor = await db.execute('SELECT * FROM bot_stats WHERE date = ?', (today,))
            today_stats_row = await cursor.fetchone()
            today_stats = dict(today_stats_row) if today_stats_row else {}
            
            return {
                'total_users': total_users,
                'total_games': total_games,
                'total_bets': total_bets,
                'project_income': project_income,
                'total_deposits': total_deposits,
                'total_withdrawals': total_withdrawals,
                'today_stats': today_stats
            }
    
    # Методы для медиа
    async def add_media(self, section: str, file_type: str, file_id: str, caption: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO media (section, file_type, file_id, caption)
                VALUES (?, ?, ?, ?)
            ''', (section, file_type, file_id, caption))
            await db.commit()
    
    async def get_media(self, section: str) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM media WHERE section = ? ORDER BY created_at DESC LIMIT 1
            ''', (section,))
            row = await cursor.fetchone()
            return dict(row) if row else None

db = Database()