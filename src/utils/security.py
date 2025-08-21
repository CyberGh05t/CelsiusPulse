"""
Утилиты безопасности для CelsiusPulse Bot
Защита от различных типов атак и мониторинг подозрительной активности
"""
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Optional
from src.config.settings import RATE_LIMIT_PER_MINUTE, ENABLE_RATE_LIMITING
from src.config.logging import SecureLogger

logger = SecureLogger(__name__)

# Глобальные счетчики для rate limiting
user_request_counts: Dict[int, deque] = defaultdict(deque)
blocked_users: Dict[int, datetime] = {}
suspicious_activity: Dict[int, int] = defaultdict(int)


class RateLimiter:
    """Система ограничения частоты запросов"""
    
    @staticmethod
    def is_rate_limited(chat_id: int) -> bool:
        """
        Проверяет, превышен ли лимит запросов для пользователя
        
        Args:
            chat_id: ID чата пользователя
            
        Returns:
            True если лимит превышен
        """
        if not ENABLE_RATE_LIMITING:
            return False
        
        current_time = time.time()
        minute_ago = current_time - 60
        
        # Очищаем старые записи
        while (user_request_counts[chat_id] and 
               user_request_counts[chat_id][0] < minute_ago):
            user_request_counts[chat_id].popleft()
        
        # Проверяем лимит
        if len(user_request_counts[chat_id]) >= RATE_LIMIT_PER_MINUTE:
            logger.warning(f"Rate limit exceeded for user {chat_id}")
            return True
        
        # Добавляем текущий запрос
        user_request_counts[chat_id].append(current_time)
        return False
    
    @staticmethod
    def block_user(chat_id: int, duration_minutes: int = 10):
        """
        Временно блокирует пользователя
        
        Args:
            chat_id: ID чата пользователя
            duration_minutes: Длительность блокировки в минутах
        """
        blocked_until = datetime.now() + timedelta(minutes=duration_minutes)
        blocked_users[chat_id] = blocked_until
        logger.warning(f"User {chat_id} blocked until {blocked_until}")
    
    @staticmethod
    def is_user_blocked(chat_id: int) -> bool:
        """
        Проверяет, заблокирован ли пользователь
        
        Args:
            chat_id: ID чата пользователя
            
        Returns:
            True если пользователь заблокирован
        """
        # Никогда не блокируем big_boss пользователей
        from src.core.auth import BIG_BOSS
        if chat_id in BIG_BOSS:
            return False
            
        if chat_id not in blocked_users:
            return False
        
        if datetime.now() >= blocked_users[chat_id]:
            # Блокировка истекла
            del blocked_users[chat_id]
            return False
        
        return True
    
    @staticmethod
    def unblock_user(chat_id: int):
        """
        Разблокирует пользователя
        
        Args:
            chat_id: ID чата пользователя
        """
        if chat_id in blocked_users:
            del blocked_users[chat_id]
            logger.info(f"User {chat_id} unblocked")
        
        if chat_id in suspicious_activity:
            del suspicious_activity[chat_id]
            logger.info(f"Suspicious activity counter reset for user {chat_id}")


class SecurityMonitor:
    """Мониторинг подозрительной активности"""
    
    @staticmethod
    def log_suspicious_activity(chat_id: int, activity_type: str, details: str = ""):
        """
        Логирует подозрительную активность
        
        Args:
            chat_id: ID чата пользователя
            activity_type: Тип подозрительной активности
            details: Дополнительные детали
        """
        suspicious_activity[chat_id] += 1
        logger.warning(
            f"Suspicious activity detected",
            extra={
                'chat_id': chat_id,
                'activity_type': activity_type,
                'details': details,
                'total_incidents': suspicious_activity[chat_id]
            }
        )
        
        # Автоматическая блокировка при превышении порога
        if suspicious_activity[chat_id] >= 5:
            RateLimiter.block_user(chat_id, duration_minutes=30)
            logger.critical(f"User {chat_id} auto-blocked due to repeated suspicious activity")
    
    @staticmethod
    def check_command_injection(text: str) -> bool:
        """
        Проверяет текст на попытки command injection
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если обнаружена попытка injection
        """
        dangerous_patterns = [
            ';', '|', '&', '$', '`', '$(', '${',
            'rm ', 'sudo ', 'chmod ', 'wget ', 'curl ',
            '../', '..\\', '/etc/', 'c:\\', 'cmd.exe',
            'powershell', '/bin/', 'bash', 'sh '
        ]
        
        text_lower = text.lower()
        for pattern in dangerous_patterns:
            if pattern in text_lower:
                return True
        
        return False
    
    @staticmethod
    def check_sql_injection(text: str) -> bool:
        """
        Проверяет текст на попытки SQL injection
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если обнаружена попытка injection
        """
        sql_patterns = [
            'union select', 'drop table', 'insert into', 'update set',
            'delete from', 'exec ', 'execute ', 'sp_', 'xp_',
            "' or '1'='1", '" or "1"="1', '1=1', '1=1--',
            'information_schema', 'sys.', 'master..'
        ]
        
        text_lower = text.lower()
        for pattern in sql_patterns:
            if pattern in text_lower:
                return True
        
        return False


def validate_request_security(chat_id: int, text: str) -> tuple[bool, Optional[str]]:
    """
    Комплексная проверка безопасности запроса
    
    Args:
        chat_id: ID чата пользователя
        text: Текст запроса
        
    Returns:
        Tuple (is_safe, error_message)
    """
    # Проверка блокировки пользователя
    if RateLimiter.is_user_blocked(chat_id):
        return False, "Пользователь временно заблокирован"
    
    # Проверка rate limit
    if RateLimiter.is_rate_limited(chat_id):
        SecurityMonitor.log_suspicious_activity(
            chat_id, "rate_limit_exceeded", 
            f"Too many requests: {len(user_request_counts[chat_id])}"
        )
        RateLimiter.block_user(chat_id, duration_minutes=5)
        return False, "Превышен лимит запросов"
    
    # Исключаем проверку injection для callback_data с регистрацией
    if text.startswith(('confirm_registration:', 'reject_registration:', 'toggle_group:')):
        return True, None
    
    # Проверка на command injection
    if SecurityMonitor.check_command_injection(text):
        SecurityMonitor.log_suspicious_activity(
            chat_id, "command_injection_attempt", 
            f"Suspicious text: {text[:100]}"
        )
        return False, "Обнаружена попытка injection атаки"
    
    # Проверка на SQL injection
    if SecurityMonitor.check_sql_injection(text):
        SecurityMonitor.log_suspicious_activity(
            chat_id, "sql_injection_attempt",
            f"Suspicious SQL pattern: {text[:100]}"
        )
        return False, "Обнаружена попытка SQL injection"
    
    return True, None


def get_security_stats() -> dict:
    """
    Возвращает статистику безопасности
    
    Returns:
        Словарь со статистикой
    """
    return {
        'active_users': len(user_request_counts),
        'blocked_users': len(blocked_users),
        'suspicious_users': len(suspicious_activity),
        'total_suspicious_incidents': sum(suspicious_activity.values())
    }


def detect_invalid_content(text: str) -> str:
    """
    Обнаруживает различные типы невалидного контента в текстовых сообщениях
    
    Args:
        text: Текст сообщения для проверки
        
    Returns:
        Строка с типом найденного невалидного контента или пустая строка если контент валидный
    """
    import re
    
    if not text or not isinstance(text, str):
        return ""
    
    text_lower = text.lower().strip()
    
    # Проверка на URL и ссылки
    url_patterns = [
        r'https?://',
        r'www\.',
        r'\.com',
        r'\.ru', 
        r'\.org',
        r'\.net',
        r't\.me',
        r'telegram\.me',
        r'@[a-zA-Z0-9_]+',  # упоминания пользователей
    ]
    
    for pattern in url_patterns:
        if re.search(pattern, text_lower):
            return "🔗 ссылка"
    
    # Проверка на спам-слова
    spam_words = [
        'реклама', 'продам', 'купи', 'скидка', 'акция', 'бонус',
        'заработок', 'деньги', 'доллар', 'биткоин', 'криптовалюта',
        'млм', 'сетевой маркетинг', 'пирамида'
    ]
    
    for spam_word in spam_words:
        if spam_word in text_lower:
            return "📢 рекламный контент"
    
    # Проверка на файловые расширения
    file_extensions = ['.exe', '.bat', '.cmd', '.scr', '.zip', '.rar']
    for ext in file_extensions:
        if ext in text_lower:
            return "📎 подозрительный файл"
    
    return ""