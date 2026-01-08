import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    BOT_TOKEN: str = "8315662398:AAFH8cYtNDHW0lwB_vD0UcdS5qDsZh6sK8M"
    CRYPTOPAY_TOKEN: str = "510583:AABMfEm7V2UKuc25lpcm6p8cYkXVhVfG42u"
    ADMIN_IDS: list = None
    
    def __post_init__(self):
        if self.ADMIN_IDS is None:
            self.ADMIN_IDS = [882242942]  # Замените на ваш ID
    
    DB_PATH: str = "database.db"
    PROJECT_PERCENTAGE: float = 0.10  # 10% проекту
    WINNER_PERCENTAGE: float = 0.90   # 90% победителю
    
config = Config()