"""
Модуль авторизации и управления ролями пользователей
Безопасная работа с группами пользователей и администраторов
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Union
from src.config.settings import ADMINS_FILE
from src.config.logging import SecureLogger
from src.utils.validators import validate_chat_id

logger = SecureLogger(__name__)

# Глобальные переменные для кеширования групп
ADMIN_GROUPS: Dict[int, List[str]] = {}
BIG_BOSS: Set[int] = set()


def load_groups() -> Dict[str, Union[Dict[int, str], Dict[int, List[str]], Set[int]]]:
    """
    Загружает группы пользователей из переменных окружения
    
    Returns:
        Словарь с группами пользователей
    """
    logger.debug("Начало загрузки групп пользователей из .env")
    try:
        # Загружаем администраторов
        admin_groups_raw = json.loads(os.getenv("ADMIN_GROUPS", "{}"))
        admin_groups = {}
        for k, v in admin_groups_raw.items():
            if validate_chat_id(k):
                admin_groups[int(k)] = v if isinstance(v, list) else [v]
            else:
                logger.warning(f"Invalid chat_id in ADMIN_GROUPS: {k}")
        
        # Загружаем big boss
        big_boss_raw = json.loads(os.getenv("BIG_BOSS", "[]"))
        big_boss = set()
        for boss_id in big_boss_raw:
            if validate_chat_id(boss_id):
                big_boss.add(int(boss_id))
            else:
                logger.warning(f"Invalid chat_id in BIG_BOSS: {boss_id}")
        
        # Обычные пользователи больше не поддерживаются
        
        logger.info("Группы пользователей успешно загружены из .env")
        return {
            "ADMIN_GROUPS": admin_groups,
            "BIG_BOSS": big_boss
        }
    except json.JSONDecodeError as e:
        logger.critical(f"Ошибка парсинга JSON в переменных окружения: {e}")
        raise
    except Exception as e:
        logger.critical(f"Ошибка загрузки групп из .env: {str(e)}")
        raise


def initialize_groups():
    """Инициализирует глобальные переменные групп"""
    global ADMIN_GROUPS, BIG_BOSS
    
    logger.info("Инициализация групп пользователей...")
    groups = load_groups()
    ADMIN_GROUPS = groups["ADMIN_GROUPS"]
    BIG_BOSS = groups["BIG_BOSS"]
    
    logger.debug(f"Загружено: {len(ADMIN_GROUPS)} администраторов, {len(BIG_BOSS)} big_boss")


def get_current_admin_groups():
    """Возвращает актуальные группы администраторов"""
    return ADMIN_GROUPS

def get_current_big_boss():
    """Возвращает актуальный список big_boss"""
    return BIG_BOSS

def get_user_role(chat_id: int) -> str:
    """
    Определяет роль пользователя
    
    Args:
        chat_id: ID чата пользователя
        
    Returns:
        Роль: 'big_boss', 'admin', 'unregistered'
    """
    if not validate_chat_id(chat_id):
        logger.warning(f"Invalid chat_id provided: {chat_id}")
        return 'unregistered'
    
    # Получаем актуальные значения из глобальных переменных
    current_big_boss = get_current_big_boss()
    current_admin_groups = get_current_admin_groups()
    
    logger.debug(f"Проверка роли для chat_id: {chat_id}")
    logger.debug(f"BIG_BOSS содержит: {current_big_boss}")
    logger.debug(f"ADMIN_GROUPS содержит: {current_admin_groups}")
    
    if chat_id in current_big_boss:
        logger.debug(f"Определена роль big_boss для chat_id: {chat_id}")
        return "big_boss"
    if chat_id in current_admin_groups:
        logger.debug(f"Определена роль admin для chat_id: {chat_id}")
        return "admin"
    
    logger.debug(f"Определена роль unregistered для chat_id: {chat_id}")
    return "unregistered"


def get_user_group(chat_id: int) -> str:
    """
    Получает группу пользователя
    
    Args:
        chat_id: ID чата пользователя
        
    Returns:
        Название группы или пустая строка
    """
    if not validate_chat_id(chat_id):
        logger.warning(f"Invalid chat_id provided: {chat_id}")
        return ""
    
    role = get_user_role(chat_id)
    
    if role == "admin":
        admin_groups = get_current_admin_groups()
        groups = admin_groups.get(chat_id, [])
        logger.debug(f"Группы администратора {chat_id}: {groups}")
        return ", ".join(groups) if groups else ""
    
    # big_boss не привязан к конкретной группе
    return ""


def is_authorized(chat_id: int, required_role: str = "admin") -> bool:
    """
    Проверяет авторизацию пользователя
    
    Args:
        chat_id: ID чата пользователя
        required_role: Минимальная требуемая роль
        
    Returns:
        True если пользователь авторизован
    """
    if not validate_chat_id(chat_id):
        return False
    
    role = get_user_role(chat_id)
    
    role_hierarchy = {
        'admin': 1,
        'big_boss': 2
    }
    
    user_level = role_hierarchy.get(role, -1)
    required_level = role_hierarchy.get(required_role, 1)
    
    return user_level >= required_level


def can_access_group(chat_id: int, group_name: str) -> bool:
    """
    Проверяет, может ли пользователь получить доступ к группе
    
    Args:
        chat_id: ID чата пользователя
        group_name: Название группы
        
    Returns:
        True если доступ разрешен
    """
    if not validate_chat_id(chat_id):
        return False
    
    role = get_user_role(chat_id)
    
    # Big boss имеет доступ ко всем группам
    if role == "big_boss":
        return True
    
    # Админы имеют доступ только к своим группам
    if role == "admin":
        admin_groups = ADMIN_GROUPS.get(chat_id, [])
        return group_name in admin_groups
    
    return False


def add_user_to_group(chat_id: int, group_name: str) -> bool:
    """
    Добавляет пользователя в группу (только для новых пользователей)
    
    Args:
        chat_id: ID чата пользователя
        group_name: Название группы
        
    Returns:
        True если пользователь добавлен успешно
    """
    if not validate_chat_id(chat_id):
        logger.error(f"Invalid chat_id for adding to group: {chat_id}")
        return False
    
    # Обычные пользователи больше не поддерживаются - только admin и big_boss
    logger.warning(f"Regular users no longer supported. Use admin roles instead.")
    return False


def get_all_users_by_role(role: str) -> Dict[int, Union[str, List[str]]]:
    """
    Возвращает всех пользователей с указанной ролью
    
    Args:
        role: Роль ('admin', 'big_boss')
        
    Returns:
        Словарь пользователей
    """
    if role == "admin":
        return ADMIN_GROUPS.copy()
    elif role == "big_boss":
        return {user_id: "big_boss" for user_id in BIG_BOSS}
    else:
        return {}


def get_users_in_group(group_name: str) -> List[int]:
    """
    Возвращает список пользователей в группе
    
    Args:
        group_name: Название группы
        
    Returns:
        Список chat_id пользователей
    """
    users = []
    
    # Поиск среди администраторов
    current_admin_groups = get_current_admin_groups()
    for chat_id, admin_groups in current_admin_groups.items():
        if group_name in admin_groups:
            users.append(chat_id)
    
    # Big boss имеет доступ ко всем группам
    current_big_boss = get_current_big_boss()
    users.extend(list(current_big_boss))
    
    return users


def get_user_accessible_groups(chat_id: int) -> List[str]:
    """
    Возвращает список групп, к которым пользователь имеет доступ
    
    Args:
        chat_id: ID чата пользователя
        
    Returns:
        Список названий групп
    """
    if not validate_chat_id(chat_id):
        return []
    
    role = get_user_role(chat_id)
    
    # Big boss имеет доступ ко всем группам
    if role == "big_boss":
        from src.core.monitoring import get_all_groups
        return get_all_groups()
    
    # Администраторы видят только свои группы (отсортированные по алфавиту)
    if role == "admin":
        admin_groups = ADMIN_GROUPS.get(chat_id, [])
        return sorted(admin_groups)
    
    # Незарегистрированные пользователи не видят ничего
    return []


def update_env_file():
    """Обновляет .env файл с текущими группами пользователей"""
    logger.info("Старт обновления .env файла")
    try:
        env_lines = []
        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                env_lines = f.readlines()
        
        sections = {
            "ADMIN_GROUPS": json.dumps({str(k): v for k, v in get_current_admin_groups().items()}, ensure_ascii=False),
            "BIG_BOSS": json.dumps(list(get_current_big_boss()), ensure_ascii=False)
        }
        
        for section, value in sections.items():
            found = False
            # Ищем в обратном порядке, чтобы найти последнюю (активную) строку
            for i in reversed(range(len(env_lines))):
                line = env_lines[i].strip()
                # Ищем незакомментированную строку с нужной секцией
                if line.startswith(f"{section}=") and not line.startswith("#"):
                    env_lines[i] = f"{section}={value}\n"
                    found = True
                    logger.debug(f"Обновлена строка {i}: {section}={value}")
                    break
            if not found:
                env_lines.append(f"{section}={value}\n")
                logger.debug(f"Добавлена новая строка: {section}={value}")
        
        with open(".env", "w", encoding="utf-8") as f:
            f.writelines(env_lines)
        
        logger.info(".env файл успешно обновлен")
    except Exception as e:
        logger.error(f"Ошибка обновления .env файла: {str(e)}")
        raise