"""
Сервис для централизованной логики бота
"""
from typing import Optional, Dict, Any, List
from src.core.menu_manager import menu_manager
from src.core.registration_manager import registration_manager
from src.core.threshold_context_manager import threshold_context_manager
from src.core.auth import get_user_role, get_user_accessible_groups
from src.core.storage import AdminManager
from src.config.logging import SecureLogger

logger = SecureLogger(__name__)


class BotService:
    """Централизованная бизнес-логика бота"""
    
    @staticmethod
    def is_user_registered(chat_id: int) -> bool:
        """Проверяет, зарегистрирован ли пользователь"""
        admin_info = AdminManager.load_admin_info(chat_id)
        return admin_info is not None and 'fio' in admin_info
    
    @staticmethod
    def can_access_menu(chat_id: int, menu_type: str) -> bool:
        """
        Проверяет доступ пользователя к определенному типу меню
        
        Args:
            chat_id: ID чата пользователя
            menu_type: Тип меню для проверки
            
        Returns:
            True если доступ разрешен
        """
        # Если пользователь в процессе регистрации
        if registration_manager.is_in_registration(chat_id):
            return menu_type in ['registration', 'main']
        
        # Если пользователь не зарегистрирован
        if not BotService.is_user_registered(chat_id):
            return menu_type in ['registration', 'start']
        
        # Зарегистрированные пользователи имеют доступ ко всем меню
        role = get_user_role(chat_id)
        return role in ['admin', 'big_boss']
    
    @staticmethod
    def get_user_stats(chat_id: int) -> Dict[str, Any]:
        """
        Получает статистику пользователя
        
        Returns:
            Словарь со статистикой пользователя
        """
        stats = {
            'is_registered': BotService.is_user_registered(chat_id),
            'role': get_user_role(chat_id),
            'in_registration': registration_manager.is_in_registration(chat_id),
            'has_active_menu': menu_manager.get_menu(chat_id) is not None,
            'has_threshold_context': threshold_context_manager.has_context(chat_id),
            'accessible_groups': get_user_accessible_groups(chat_id) if BotService.is_user_registered(chat_id) else [],
        }
        
        # Добавляем информацию о текущем меню
        current_menu = menu_manager.get_menu(chat_id)
        if current_menu:
            stats['current_menu'] = {
                'type': current_menu.menu_type,
                'context': current_menu.menu_context,
                'age_seconds': int(__import__('time').time() - current_menu.timestamp)
            }
        
        # Добавляем информацию о регистрации
        if registration_manager.is_in_registration(chat_id):
            reg_state = registration_manager.get_registration_state(chat_id)
            if reg_state:
                stats['registration'] = {
                    'step': reg_state.registration_step,
                    'has_fio': reg_state.fio is not None,
                    'selected_groups_count': len(reg_state.selected_groups)
                }
        
        return stats
    
    @staticmethod
    def get_system_stats() -> Dict[str, Any]:
        """
        Получает общую статистику системы
        
        Returns:
            Словарь с системной статистикой
        """
        # Очищаем истекшие данные
        expired_menus = menu_manager.clear_expired_menus()
        expired_registrations = registration_manager.clear_expired_registrations()
        expired_contexts = threshold_context_manager.clear_expired_contexts()
        
        stats = {
            'active_menus': menu_manager.get_active_users_count(),
            'active_registrations': registration_manager.get_active_registrations_count(),
            'active_threshold_contexts': threshold_context_manager.get_active_contexts_count(),
            'expired_cleaned': {
                'menus': expired_menus,
                'registrations': expired_registrations,
                'threshold_contexts': expired_contexts
            },
            'menu_type_distribution': menu_manager.get_menu_stats(),
            'registration_step_distribution': registration_manager.get_registration_stats(),
        }
        
        # Добавляем статистику пользователей
        try:
            all_admins = AdminManager.get_all_admins()
            stats['registered_users_count'] = len(all_admins)
            
            # Статистика по ролям
            role_stats = {}
            for admin in all_admins:
                role = admin.get('role', 'unknown')
                role_stats[role] = role_stats.get(role, 0) + 1
            stats['role_distribution'] = role_stats
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики пользователей: {e}")
            stats['registered_users_count'] = 0
            stats['role_distribution'] = {}
        
        return stats
    
    @staticmethod
    async def cleanup_expired_data():
        """Очищает все истекшие данные (для периодического запуска)"""
        try:
            expired_menus = menu_manager.clear_expired_menus()
            expired_registrations = registration_manager.clear_expired_registrations()
            expired_contexts = threshold_context_manager.clear_expired_contexts()
            
            total_cleaned = expired_menus + expired_registrations + expired_contexts
            
            if total_cleaned > 0:
                logger.info(f"Очищено истекших данных: {total_cleaned} (меню: {expired_menus}, регистрации: {expired_registrations}, контексты: {expired_contexts})")
            
            return total_cleaned
            
        except Exception as e:
            logger.error(f"Ошибка очистки истекших данных: {e}")
            return 0
    
    @staticmethod
    def validate_threshold_input(text: str) -> tuple[bool, Optional[str], Optional[float], Optional[float]]:
        """
        Валидирует ввод пороговых значений
        
        Args:
            text: Введенный текст
            
        Returns:
            Кортеж (успех, ошибка, мин_значение, макс_значение)
        """
        parts = text.strip().split()
        
        if len(parts) != 2:
            return False, "Неверный формат. Введите два числа через пробел: мин макс", None, None
        
        try:
            min_temp = float(parts[0])
            max_temp = float(parts[1])
        except ValueError:
            return False, "Значения должны быть числами", None, None
        
        if min_temp >= max_temp:
            return False, "Минимальное значение должно быть меньше максимального", None, None
        
        if min_temp < -50 or max_temp > 100:
            return False, "Значения должны быть в диапазоне от -50°C до 100°C", None, None
        
        return True, None, min_temp, max_temp
    
    @staticmethod
    def get_user_menu_breadcrumbs(chat_id: int) -> List[str]:
        """
        Возвращает "хлебные крошки" текущего местоположения пользователя в меню
        
        Returns:
            Список строк с путем по меню
        """
        breadcrumbs = ["Главное меню"]
        
        current_menu = menu_manager.get_menu(chat_id)
        if not current_menu:
            return breadcrumbs
        
        menu_type = current_menu.menu_type
        context = current_menu.menu_context
        
        if menu_type == "help":
            breadcrumbs.append("Помощь")
        elif menu_type == "info":
            breadcrumbs.append("Информация")
        elif menu_type == "thresholds":
            breadcrumbs.append("Пороговые значения")
        elif menu_type == "group_devices":
            group_name = context.get('group_name', 'Группа')
            breadcrumbs.extend(["Пороговые значения", f"Группа {group_name}"])
        elif menu_type == "device_threshold":
            group_name = context.get('group_name', 'Группа')
            device_id = context.get('device_id', 'Устройство')
            breadcrumbs.extend(["Пороговые значения", f"Группа {group_name}", f"Устройство {device_id}"])
        elif menu_type == "registration":
            step = registration_manager.get_registration_step(chat_id)
            breadcrumbs.append(f"Регистрация ({step})")
        
        return breadcrumbs