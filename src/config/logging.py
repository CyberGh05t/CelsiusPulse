"""
Настройка системы логирования для CelsiusPulse Bot
Включает безопасное логирование без раскрытия секретов
"""
import logging
from logging.handlers import RotatingFileHandler
from .settings import LOG_FILE, LOG_LEVEL, LOG_MAX_BYTES, LOG_BACKUP_COUNT, DEBUG


def setup_logging():
    """Настройка системы логирования с ротацией файлов"""
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Файловый обработчик с ротацией
    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        mode="a",
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
        delay=True
    )
    file_handler.setFormatter(formatter)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if DEBUG else getattr(logging, LOG_LEVEL.upper()))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def secure_log_data(data: dict) -> dict:
    """
    Маскирует чувствительные данные в логах
    
    Args:
        data: Словарь с данными для логирования
        
    Returns:
        Словарь с замаскированными чувствительными данными
    """
    if not isinstance(data, dict):
        return data
    
    sensitive_keys = [
        'token', 'password', 'key', 'secret', 'api_key',
        'telegram_bot_token', 'chat_id', 'user_id'
    ]
    
    masked_data = data.copy()
    for key, value in masked_data.items():
        if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
            if isinstance(value, str) and len(value) > 8:
                # Показываем только первые и последние 4 символа
                masked_data[key] = f"{value[:4]}***{value[-4:]}"
            else:
                masked_data[key] = "***MASKED***"
    
    return masked_data


class SecureLogger:
    """Безопасный логгер с автоматической маскировкой чувствительных данных"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def info(self, message: str, extra: dict = None):
        if extra:
            extra = secure_log_data(extra)
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, extra: dict = None):
        if extra:
            extra = secure_log_data(extra)
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, extra: dict = None):
        if extra:
            extra = secure_log_data(extra)
        self.logger.error(message, extra=extra)
    
    def critical(self, message: str, extra: dict = None):
        if extra:
            extra = secure_log_data(extra)
        self.logger.critical(message, extra=extra)
    
    def debug(self, message: str, extra: dict = None):
        if extra:
            extra = secure_log_data(extra)
        self.logger.debug(message, extra=extra)