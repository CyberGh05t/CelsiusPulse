"""
Конфигурация приложения CelsiusPulse Bot
Загрузка переменных окружения и констант
"""
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Telegram настройки
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")

# API настройки
DOGET_URL = os.getenv("DOGET_URL")
if not DOGET_URL:
    raise ValueError("DOGET_URL не найден в переменных окружения")

# Файлы данных
DATA_DIR = "data"
THRESHOLDS_FILE = os.path.join(DATA_DIR, "thresholds.json")
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")
LOG_FILE = os.path.join(DATA_DIR, "logs", "bot.log")

# Лимиты безопасности
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "4000"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "50"))
ENABLE_RATE_LIMITING = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"

# Настройки мониторинга
MONITORING_INTERVAL = int(os.getenv("MONITORING_INTERVAL", "60"))  # секунды
ALERT_COOLDOWN = int(os.getenv("ALERT_COOLDOWN", "600"))  # 10 минут

# Настройки логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "5242880"))  # 5MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "3"))

# Проверяем наличие обязательных директорий
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)