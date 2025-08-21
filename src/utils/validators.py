"""
Утилиты для валидации входных данных
Защита от различных типов атак и вредоносного ввода
"""
import re
from typing import Any
from src.config.settings import MAX_MESSAGE_LENGTH


def validate_user_input(text: str) -> bool:
    """
    Валидирует пользовательский ввод на предмет безопасности
    
    Args:
        text: Входная строка от пользователя
        
    Returns:
        True если ввод безопасен, False в противном случае
    """
    if not isinstance(text, str):
        return False
    
    # Проверка длины
    if len(text) > MAX_MESSAGE_LENGTH:
        return False
    
    # Проверка на пустую строку
    if not text.strip():
        return False
    
    # Проверка на потенциально опасные символы
    dangerous_chars = ['<', '>', '&', '"', "'", ';', '|', '`', '$']
    if any(char in text for char in dangerous_chars):
        return False
    
    # Проверка на SQL injection паттерны
    sql_patterns = [
        r'\bunion\b', r'\bselect\b', r'\bdrop\b', r'\binsert\b',
        r'\bupdate\b', r'\bdelete\b', r'\bexec\b', r'\bscript\b'
    ]
    text_lower = text.lower()
    for pattern in sql_patterns:
        if re.search(pattern, text_lower):
            return False
    
    # Проверка на command injection
    if any(cmd in text_lower for cmd in ['rm ', 'sudo ', 'chmod ', 'wget ', 'curl ']):
        return False
    
    return True


def validate_chat_id(chat_id: Any) -> bool:
    """
    Валидирует chat_id Telegram
    
    Args:
        chat_id: ID чата
        
    Returns:
        True если chat_id валиден
    """
    if not isinstance(chat_id, int):
        try:
            chat_id = int(chat_id)
        except (ValueError, TypeError):
            return False
    
    # Telegram chat_id обычно в диапазоне от -999999999999 до 999999999999
    return -999999999999 <= chat_id <= 999999999999


def validate_temperature(temp: Any) -> bool:
    """
    Валидирует значение температуры
    
    Args:
        temp: Значение температуры
        
    Returns:
        True если температура валидна
    """
    try:
        temp_float = float(temp)
        # Разумные пределы температуры для складских помещений
        return -100 <= temp_float <= 100
    except (ValueError, TypeError):
        return False


def validate_device_id(device_id: str) -> bool:
    """
    Валидирует ID устройства
    
    Args:
        device_id: Идентификатор устройства
        
    Returns:
        True если device_id валиден
    """
    if not isinstance(device_id, str):
        return False
    
    # Проверяем формат: только буквы, цифры, подчеркивания, дефисы
    pattern = r'^[a-zA-Z0-9_-]+$'
    if not re.match(pattern, device_id):
        return False
    
    # Проверяем длину
    return 1 <= len(device_id) <= 50


def validate_group_name(group: str) -> bool:
    """
    Валидирует название группы
    
    Args:
        group: Название группы
        
    Returns:
        True если название группы валидно
    """
    if not isinstance(group, str):
        return False
    
    # Проверяем формат: буквы, цифры, пробелы, дефисы
    pattern = r'^[a-zA-Z0-9\s_-]+$'
    if not re.match(pattern, group):
        return False
    
    # Проверяем длину
    return 1 <= len(group) <= 30


def sanitize_string(text: str) -> str:
    """
    Очищает строку от потенциально опасных символов
    
    Args:
        text: Входная строка
        
    Returns:
        Очищенная строка
    """
    if not isinstance(text, str):
        return ""
    
    # Удаляем потенциально опасные символы
    dangerous_chars = ['<', '>', '&', '"', "'", ';', '|', '`']
    for char in dangerous_chars:
        text = text.replace(char, '')
    
    # Обрезаем пробелы
    text = text.strip()
    
    # Ограничиваем длину
    return text[:MAX_MESSAGE_LENGTH]


def escape_markdown(text: str) -> str:
    """
    Экранирует специальные символы Markdown для безопасного отображения
    
    Args:
        text: Текст для экранирования
        
    Returns:
        Экранированный текст
    """
    if not isinstance(text, str):
        return ""
    
    # Экранируем символы маркдауна
    markdown_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in markdown_chars:
        text = text.replace(char, f'\\{char}')
    
    return text


def validate_json_structure(data: dict, required_fields: list) -> bool:
    """
    Валидирует структуру JSON данных
    
    Args:
        data: JSON данные для проверки
        required_fields: Список обязательных полей
        
    Returns:
        True если структура валидна
    """
    if not isinstance(data, dict):
        return False
    
    # Проверяем наличие всех обязательных полей
    for field in required_fields:
        if field not in data:
            return False
    
    return True


def validate_fio(fio: str) -> bool:
    """
    Усиленная валидация ФИО с защитой от бессмысленных данных
    
    Args:
        fio: ФИО для проверки
        
    Returns:
        True если ФИО корректно
    """
    
    if not fio or not isinstance(fio, str):
        return False
    
    fio = fio.strip()
    
    # Проверка длины
    if len(fio) < 5 or len(fio) > 100:
        return False
    
    words = fio.split()
    
    # Поддержка 3-5 слов (Фамилия Имя Отчество [Второе имя] [Приставка])
    if len(words) < 3 or len(words) > 5:
        return False
    
    # Валидация каждого слова
    for i, word in enumerate(words):
        if not word or len(word) < 2 or len(word) > 15:
            return False
        
        # Только буквы, дефисы и апострофы
        if not re.match(r'^[А-Яа-яЁёA-Za-z\-\']+$', word):
            return False
        
        # Каждое слово должно начинаться с заглавной буквы
        if not word[0].isupper():
            return False
    
    return True