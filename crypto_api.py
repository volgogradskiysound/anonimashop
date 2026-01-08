import datetime
import aiohttp
import json
from typing import Optional, Dict
from config import config

class CryptoPayAPI:
    def __init__(self):
        self.token = config.CRYPTOPAY_TOKEN
        self.base_url = f"https://pay.crypt.bot/api"
        self.headers = {
            "Crypto-Pay-API-Token": self.token
        }
    
    async def create_invoice(self, amount: float, currency: str = "USD") -> Optional[Dict]:
        """Создание инвойса для оплаты"""
        url = f"{self.base_url}/createInvoice"
        
        payload = {
            "asset": "USDT",
            "amount": str(amount),
            "description": f"Пополнение баланса на {amount} USD",
            "hidden_message": "Оплата для игры в кубики",
            "paid_btn_name": "callback",
            "paid_btn_url": "https://t.me/dice_betting_bot",
            "payload": json.dumps({"type": "deposit"})
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        return data.get("result")
                return None
    
    async def get_invoice(self, invoice_id: str) -> Optional[Dict]:
        """Проверка статуса инвойса"""
        url = f"{self.base_url}/getInvoices?invoice_ids={invoice_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        result = data.get("result", {}).get("items", [])
                        return result[0] if result else None
                return None
    
    async def transfer(self, user_id: int, amount: float, currency: str = "USD") -> Optional[Dict]:
        """Перевод средств пользователю"""
        url = f"{self.base_url}/transfer"
        
        payload = {
            "user_id": user_id,
            "asset": "USDT",
            "amount": str(amount),
            "spend_id": f"transfer_{user_id}_{int(datetime.now().timestamp())}",
            "comment": f"Выигрыш в игре {amount} USD"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        return data.get("result")
                return None

crypto_api = CryptoPayAPI()