import datetime
import random
import asyncio
from typing import Dict, Tuple
from aiogram import Bot
from config import config
from database import db
from crypto_api import crypto_api

class GameManager:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.active_games = {}
    
    async def create_room(self, user_id: int, bet_amount: float) -> Tuple[bool, str, int]:
        """Создание комнаты"""
        try:
            # Проверяем баланс пользователя
            user = await db.get_user(user_id)
            if not user:
                return False, "Пользователь не найден", 0
            
            if user['is_banned']:
                return False, "Вы забанены", 0
            
            # Создаем комнату
            room_id = await db.create_room(user_id, bet_amount)
            
            # Создаем инвойс для оплаты
            invoice = await crypto_api.create_invoice(bet_amount)
            
            if invoice:
                # Сохраняем invoice_id в комнате
                await db.update_room(room_id, invoice_id=invoice['invoice_id'])
                return True, invoice['pay_url'], room_id
            else:
                return False, "Ошибка создания платежа", 0
                
        except Exception as e:
            return False, f"Ошибка: {str(e)}", 0
    
    async def join_room(self, user_id: int, room_id: int) -> Tuple[bool, str]:
        """Присоединение к комнате"""
        try:
            room = await db.get_room(room_id)
            if not room:
                return False, "Комната не найдена"
            
            if room['status'] != 'waiting':
                return False, "Комната уже занята или игра завершена"
            
            if room['creator_id'] == user_id:
                return False, "Вы не можете присоединиться к своей комнате"
            
            # Создаем инвойс для второго игрока
            invoice = await crypto_api.create_invoice(room['bet_amount'])
            
            if invoice:
                # Обновляем комнату
                await db.update_room(
                    room_id,
                    player2_id=user_id,
                    invoice_id_2=invoice['invoice_id'],
                    status='waiting_payment'
                )
                return True, invoice['pay_url']
            else:
                return False, "Ошибка создания платежа"
                
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
    
    async def check_payment(self, room_id: int) -> Tuple[bool, str]:
        """Проверка оплаты в комнате"""
        room = await db.get_room(room_id)
        if not room:
            return False, "Комната не найдена"
        
        # Проверяем оплату первого игрока
        if not room.get('player1_paid'):
            invoice_id = room.get('invoice_id')
            if invoice_id:
                invoice = await crypto_api.get_invoice(invoice_id)
                if invoice and invoice['status'] == 'paid':
                    await db.update_room(room_id, player1_paid=1)
        
        # Проверяем оплату второго игрока
        if not room.get('player2_paid') and room.get('player2_id'):
            invoice_id_2 = room.get('invoice_id_2')
            if invoice_id_2:
                invoice = await crypto_api.get_invoice(invoice_id_2)
                if invoice and invoice['status'] == 'paid':
                    await db.update_room(room_id, player2_paid=1)
        
        # Обновляем комнату
        room = await db.get_room(room_id)
        
        if room['player1_paid'] and (room['player2_paid'] or not room['player2_id']):
            # Начинаем игру
            await self.start_game(room_id)
            return True, "Оплата подтверждена, игра начинается!"
        
        return False, "Ожидание оплаты"
    
    async def start_game(self, room_id: int):
        """Начало игры"""
        room = await db.get_room(room_id)
        
        # Бросаем кубики
        player1_dice = random.randint(1, 6)
        player2_dice = random.randint(1, 6) if room['player2_id'] else 0
        
        # Определяем победителя
        if player1_dice > player2_dice:
            winner_id = room['player1_id']
            loser_id = room['player2_id']
        elif player2_dice > player1_dice:
            winner_id = room['player2_id']
            loser_id = room['player1_id']
        else:
            winner_id = None  # Ничья
        
        # Рассчитываем приз
        total_bet = room['bet_amount'] * 2
        project_fee = total_bet * config.PROJECT_PERCENTAGE
        prize_amount = total_bet - project_fee if winner_id else total_bet
        
        # Обновляем комнату
        await db.update_room(
            room_id,
            player1_dice=player1_dice,
            player2_dice=player2_dice,
            winner_id=winner_id,
            prize_amount=prize_amount,
            status='finished',
            finished_at=datetime.now().isoformat()
        )
        
        # Записываем транзакции
        if winner_id:
            # Приз победителю
            await db.add_transaction(winner_id, prize_amount, 'win', room_id, 'Выигрыш в игре')
            await db.update_user_balance(winner_id, prize_amount)
            
            # Комиссия проекта
            await db.add_transaction(0, project_fee, 'project_fee', room_id, 'Комиссия проекта')
            
            # Обновляем статистику пользователей
            await self.update_user_stats(winner_id, True, room['bet_amount'] * 2)
            await self.update_user_stats(loser_id, False, room['bet_amount'])
        
        # Отправляем результаты игрокам
        await self.send_game_results(room_id)
    
    async def update_user_stats(self, user_id: int, win: bool, bet_amount: float):
        """Обновление статистики пользователя"""
        user = await db.get_user(user_id)
        if user:
            if win:
                await db.db.execute('''
                    UPDATE users SET 
                    total_wins = total_wins + 1,
                    total_bet = total_bet + ?
                    WHERE user_id = ?
                ''', (bet_amount, user_id))
            else:
                await db.db.execute('''
                    UPDATE users SET 
                    total_losses = total_losses + 1,
                    total_bet = total_bet + ?
                    WHERE user_id = ?
                ''', (bet_amount, user_id))
    
    async def send_game_results(self, room_id: int):
        """Отправка результатов игры"""
        room = await db.get_room(room_id)
        
        player1 = await db.get_user(room['player1_id'])
        player2 = await db.get_user(room['player2_id']) if room['player2_id'] else None
        
        message = "🎲 *Результаты игры*\n\n"
        message += f"Игрок 1: @{player1['username']} - {room['player1_dice']}\n"
        
        if player2:
            message += f"Игрок 2: @{player2['username']} - {room['player2_dice']}\n\n"
        
        if room['winner_id']:
            winner = await db.get_user(room['winner_id'])
            message += f"🏆 Победитель: @{winner['username']}\n"
            message += f"💰 Выигрыш: {room['prize_amount']} USD"
        else:
            message += "🤝 Ничья! Ставки возвращаются"
        
        # Отправляем игроку 1
        await self.bot.send_message(
            room['player1_id'],
            message,
            parse_mode='Markdown'
        )
        
        # Отправляем игроку 2 если есть
        if player2:
            await self.bot.send_message(
                room['player2_id'],
                message,
                parse_mode='Markdown'
            )