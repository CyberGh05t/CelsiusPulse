"""
Модуль для работы с хранением данных
Безопасная работа с JSON файлами и администраторской информацией
"""
import os
import json
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, List
from src.config.settings import THRESHOLDS_FILE, ADMINS_FILE
from src.config.logging import SecureLogger
from src.utils.validators import validate_chat_id, validate_json_structure

logger = SecureLogger(__name__)


def safe_json_load(file_path: str, default_value: Any = None) -> Any:
    """
    Безопасно загружает JSON файл с обработкой ошибок
    
    Args:
        file_path: Путь к JSON файлу
        default_value: Значение по умолчанию при ошибке
        
    Returns:
        Загруженные данные или default_value
    """
    try:
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}, using default value")
            return default_value
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        logger.debug(f"Successfully loaded JSON from {file_path}")
        return data
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {file_path}: {e}")
        # Создаем бекап поврежденного файла
        backup_file = f"{file_path}.corrupted_{int(datetime.now().timestamp())}"
        if os.path.exists(file_path):
            shutil.copy2(file_path, backup_file)
            logger.error(f"Corrupted file backed up as: {backup_file}")
        return default_value
    
    except Exception as e:
        logger.error(f"Error loading JSON from {file_path}: {e}")
        return default_value


def safe_json_save(file_path: str, data: Any, create_backup: bool = True) -> bool:
    """
    Безопасно сохраняет данные в JSON файл
    
    Args:
        file_path: Путь к JSON файлу
        data: Данные для сохранения
        create_backup: Создавать ли бекап существующего файла
        
    Returns:
        True если сохранение успешно
    """
    try:
        # Создаем директорию если не существует
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Создаем бекап если файл существует
        if create_backup and os.path.exists(file_path):
            backup_file = f"{file_path}.backup"
            shutil.copy2(file_path, backup_file)
        
        # Сохраняем данные
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"Successfully saved JSON to {file_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving JSON to {file_path}: {e}")
        return False


class ThresholdManager:
    """Менеджер пороговых значений температуры"""
    
    @staticmethod
    def load_thresholds() -> Dict[str, Any]:
        """
        Загружает пороговые значения из файла
        
        Returns:
            Словарь с пороговыми значениями
        """
        logger.info("Загрузка порогов из файла...")
        
        thresholds = safe_json_load(THRESHOLDS_FILE, {})
        
        # Валидация структуры данных
        if not isinstance(thresholds, dict):
            logger.warning("Invalid thresholds structure, using empty dict")
            return {}
        
        # Подсчет загруженных данных
        total_devices = 0
        total_groups = len(thresholds)
        
        for group, devices in thresholds.items():
            if isinstance(devices, dict):
                total_devices += len(devices)
        
        logger.info(f"Успешно загружено {total_devices} устройств в {total_groups} группах")
        return thresholds
    
    @staticmethod
    def save_thresholds(thresholds: Dict[str, Any]) -> bool:
        """
        Сохраняет пороговые значения в файл
        
        Args:
            thresholds: Словарь с пороговыми значениями
            
        Returns:
            True если сохранение успешно
        """
        logger.info("Сохранение порогов в файл...")
        
        if not isinstance(thresholds, dict):
            logger.error("Invalid thresholds data type")
            return False
        
        success = safe_json_save(THRESHOLDS_FILE, thresholds)
        
        if success:
            logger.info(f"Пороговые значения сохранены: {len(thresholds)} групп")
        else:
            logger.error("Ошибка сохранения пороговых значений")
        
        return success
    
    @staticmethod
    def get_device_threshold(device_id: str, group: str) -> Optional[Dict[str, float]]:
        """
        Получает пороговые значения для конкретного устройства
        
        Args:
            device_id: ID устройства
            group: Группа устройства
            
        Returns:
            Словарь с min/max значениями или None
        """
        thresholds = ThresholdManager.load_thresholds()
        
        if group in thresholds and device_id in thresholds[group]:
            return thresholds[group][device_id]
        
        return None
    
    @staticmethod
    def set_device_threshold(device_id: str, group: str, min_temp: float, max_temp: float) -> bool:
        """
        Устанавливает пороговые значения для устройства
        
        Args:
            device_id: ID устройства
            group: Группа устройства
            min_temp: Минимальная температура
            max_temp: Максимальная температура
            
        Returns:
            True если установка успешна
        """
        thresholds = ThresholdManager.load_thresholds()
        
        if group not in thresholds:
            thresholds[group] = {}
        
        thresholds[group][device_id] = {
            "min": min_temp,
            "max": max_temp
        }
        
        return ThresholdManager.save_thresholds(thresholds)


class AdminManager:
    """Менеджер информации об администраторах"""
    
    @staticmethod
    def load_admin_info(chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Загружает информацию об администраторе
        
        Args:
            chat_id: ID чата администратора
            
        Returns:
            Информация об администраторе или None
        """
        if not validate_chat_id(chat_id):
            logger.error(f"Invalid chat_id: {chat_id}")
            return None
        
        logger.info(f"Загрузка информации об администраторе {chat_id}")
        
        admins = safe_json_load(ADMINS_FILE, [])
        
        if isinstance(admins, list):
            for admin in admins:
                if isinstance(admin, dict) and admin.get("chat_id") == chat_id:
                    logger.debug(f"Найдена информация об администраторе {chat_id}")
                    return admin
        
        logger.debug(f"Информация об администраторе {chat_id} не найдена")
        # Возвращаем базовую структуру для новых администраторов
        from .auth import get_current_admin_groups
        admin_groups = get_current_admin_groups()
        return {"groups": admin_groups.get(chat_id, [])}
    
    @staticmethod
    def save_admin_info(chat_id: int, fio: str, position: str, role: str = None, groups: List[str] = None) -> bool:
        """
        Сохраняет информацию об администраторе
        
        Args:
            chat_id: ID чата администратора
            fio: ФИО администратора
            position: Должность администратора
            role: Роль администратора (опционально)
            groups: Список групп администратора (опционально)
            
        Returns:
            True если сохранение успешно
        """
        if not validate_chat_id(chat_id):
            logger.error(f"Invalid chat_id: {chat_id}")
            return False
        
        logger.info(f"Сохранение информации об администраторе {chat_id}")
        
        admins = safe_json_load(ADMINS_FILE, [])
        if not isinstance(admins, list):
            admins = []
        
        # Определяем роль и группы если не переданы
        if role is None or groups is None:
            from .auth import get_current_admin_groups, get_user_role
            if role is None:
                role = get_user_role(chat_id)
            if groups is None:
                if role == "big_boss":
                    groups = []  # У big_boss пустой список групп
                else:
                    admin_groups = get_current_admin_groups()
                    groups = admin_groups.get(chat_id, [])
        
        # Проверяем существование записи
        updated = False
        for admin in admins:
            if isinstance(admin, dict) and admin.get("chat_id") == chat_id:
                logger.debug(f"Обновление существующей записи администратора {chat_id}")
                
                admin.update({
                    "fio": fio,
                    "position": position,
                    "role": role,
                    "groups": groups,
                    "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                updated = True
                break
        
        if not updated:
            logger.debug(f"Добавление новой записи администратора {chat_id}")
            
            admins.append({
                "chat_id": chat_id,
                "fio": fio,
                "position": position,
                "role": role,
                "groups": groups,
                "registered": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        
        success = safe_json_save(ADMINS_FILE, admins)
        
        if success:
            logger.info(f"Информация об администраторе {chat_id} сохранена")
        else:
            logger.error(f"Ошибка сохранения информации об администраторе {chat_id}")
        
        return success
    
    @staticmethod
    def update_admin_roles():
        """
        Обновляет роли всех админов в admins.json на основе .env
        """
        from .auth import get_user_role, get_current_admin_groups, get_current_big_boss
        
        admins = safe_json_load(ADMINS_FILE, [])
        if not isinstance(admins, list):
            return False
        
        updated_count = 0
        for admin in admins:
            if isinstance(admin, dict) and "chat_id" in admin:
                chat_id = admin["chat_id"]
                current_role = get_user_role(chat_id)
                
                if admin.get("role") != current_role:
                    admin["role"] = current_role
                    if current_role == "big_boss":
                        admin["groups"] = []
                    else:
                        admin_groups = get_current_admin_groups()
                        admin["groups"] = admin_groups.get(chat_id, [])
                    admin["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    updated_count += 1
        
        if updated_count > 0:
            success = safe_json_save(ADMINS_FILE, admins)
            logger.info(f"Updated roles for {updated_count} admins")
            return success
        return True
    
    @staticmethod
    def get_all_admins() -> List[Dict[str, Any]]:
        """
        Возвращает информацию о всех администраторах
        
        Returns:
            Список словарей с информацией об администраторах
        """
        logger.info("Загрузка информации о всех администраторах")
        
        admins = safe_json_load(ADMINS_FILE, [])
        
        if not isinstance(admins, list):
            logger.warning("Invalid admins data structure")
            return []
        
        # Фильтруем только валидные записи
        valid_admins = []
        for admin in admins:
            if isinstance(admin, dict) and "chat_id" in admin:
                if validate_chat_id(admin["chat_id"]):
                    valid_admins.append(admin)
        
        logger.debug(f"Загружено {len(valid_admins)} валидных администраторов")
        return valid_admins
    
    @staticmethod
    def remove_admin(chat_id: int) -> bool:
        """
        Удаляет информацию об администраторе
        
        Args:
            chat_id: ID чата администратора
            
        Returns:
            True если удаление успешно
        """
        if not validate_chat_id(chat_id):
            logger.error(f"Invalid chat_id: {chat_id}")
            return False
        
        logger.info(f"Удаление администратора {chat_id}")
        
        admins = safe_json_load(ADMINS_FILE, [])
        if not isinstance(admins, list):
            return False
        
        # Фильтруем список, исключая удаляемого администратора
        updated_admins = [
            admin for admin in admins 
            if not (isinstance(admin, dict) and admin.get("chat_id") == chat_id)
        ]
        
        if len(updated_admins) < len(admins):
            success = safe_json_save(ADMINS_FILE, updated_admins)
            if success:
                logger.info(f"Администратор {chat_id} успешно удален")
            return success
        else:
            logger.warning(f"Администратор {chat_id} не найден для удаления")
            return False
    
    @staticmethod
    def save_admin(admin_data: Dict[str, Any]) -> bool:
        """
        Сохраняет данные администратора в упрощенном формате
        
        Args:
            admin_data: Словарь с данными администратора
            
        Returns:
            True если сохранение успешно
        """
        chat_id = admin_data.get('chat_id')
        fio = admin_data.get('fio', '')
        position = admin_data.get('position', '')
        groups = admin_data.get('groups', [])
        
        return AdminManager.save_admin_info(
            chat_id=chat_id,
            fio=fio,
            position=position,
            groups=groups
        )