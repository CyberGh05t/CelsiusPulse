"""
Менеджер состояний меню - замена глобальных переменных
"""
from typing import Dict, Optional, Any
from dataclasses import dataclass
import time


@dataclass
class MenuState:
    """Состояние активного меню пользователя"""
    chat_id: int
    message_id: int
    menu_type: str
    menu_context: Dict[str, Any]
    timestamp: float
    
    def is_expired(self, timeout_seconds: int = 3600) -> bool:
        """Проверяет, истекло ли время жизни меню"""
        return time.time() - self.timestamp > timeout_seconds


class MenuManager:
    """Централизованное управление состояниями меню пользователей"""
    
    def __init__(self):
        self._active_menus: Dict[int, MenuState] = {}
    
    def track_menu(
        self, 
        user_id: int, 
        chat_id: int, 
        message_id: int, 
        menu_type: str = "main", 
        menu_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Отслеживает активное меню пользователя
        
        Args:
            user_id: ID пользователя
            chat_id: ID чата
            message_id: ID сообщения с меню
            menu_type: Тип меню (main, settings, thresholds, etc.)
            menu_context: Дополнительный контекст меню
        """
        if menu_context is None:
            menu_context = {}
        
        self._active_menus[user_id] = MenuState(
            chat_id=chat_id,
            message_id=message_id,
            menu_type=menu_type,
            menu_context=menu_context,
            timestamp=time.time()
        )
    
    def get_menu(self, user_id: int) -> Optional[MenuState]:
        """
        Получает информацию о последнем активном меню пользователя
        
        Returns:
            MenuState или None если меню не найдено
        """
        menu_state = self._active_menus.get(user_id)
        
        # Удаляем истекшие меню
        if menu_state and menu_state.is_expired():
            self.clear_menu(user_id)
            return None
            
        return menu_state
    
    def get_menu_context(self, user_id: int) -> Dict[str, Any]:
        """
        Получает контекст активного меню пользователя
        
        Returns:
            Контекст меню или пустой словарь
        """
        menu_state = self.get_menu(user_id)
        return menu_state.menu_context if menu_state else {}
    
    def get_menu_type(self, user_id: int) -> str:
        """
        Получает тип активного меню пользователя
        
        Returns:
            Тип меню или 'unknown'
        """
        menu_state = self.get_menu(user_id)
        return menu_state.menu_type if menu_state else 'unknown'
    
    def is_menu_type(self, user_id: int, expected_type: str) -> bool:
        """
        Проверяет, является ли активное меню пользователя указанным типом
        
        Args:
            user_id: ID пользователя
            expected_type: Ожидаемый тип меню
            
        Returns:
            True если активное меню соответствует типу
        """
        return self.get_menu_type(user_id) == expected_type
    
    def clear_menu(self, user_id: int) -> None:
        """Очищает активное меню пользователя"""
        self._active_menus.pop(user_id, None)
    
    def clear_expired_menus(self) -> int:
        """
        Очищает все истекшие меню
        
        Returns:
            Количество очищенных меню
        """
        expired_users = [
            user_id for user_id, menu_state in self._active_menus.items()
            if menu_state.is_expired()
        ]
        
        for user_id in expired_users:
            self.clear_menu(user_id)
        
        return len(expired_users)
    
    def get_active_users_count(self) -> int:
        """Возвращает количество пользователей с активными меню"""
        return len(self._active_menus)
    
    def get_menu_stats(self) -> Dict[str, int]:
        """
        Возвращает статистику по типам активных меню
        
        Returns:
            Словарь {тип_меню: количество}
        """
        stats = {}
        for menu_state in self._active_menus.values():
            menu_type = menu_state.menu_type
            stats[menu_type] = stats.get(menu_type, 0) + 1
        return stats


# Глобальный экземпляр менеджера меню
menu_manager = MenuManager()