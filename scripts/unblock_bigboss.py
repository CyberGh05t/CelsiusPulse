#!/usr/bin/env python3
"""
Скрипт для разблокировки big_boss если он был заблокирован системой безопасности
"""
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.utils.security import RateLimiter

def main():
    # Получаем ID из переменной окружения
    approver_id = os.getenv('REGISTRATION_APPROVER_ID')
    
    if not approver_id:
        print("❌ REGISTRATION_APPROVER_ID не задан в .env файле")
        return
    
    try:
        big_boss_id = int(approver_id)
    except ValueError:
        print(f"❌ Неверный формат REGISTRATION_APPROVER_ID: {approver_id}")
        return
    
    print(f"Разблокировка пользователя {big_boss_id}...")
    RateLimiter.unblock_user(big_boss_id)
    print("✅ Big Boss разблокирован!")

if __name__ == "__main__":
    main()