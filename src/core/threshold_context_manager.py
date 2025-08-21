"""
Менеджер контекста пороговых значений - замена глобальных переменных
"""
from typing import Dict, Optional, Any
from dataclasses import dataclass
import time


@dataclass
class ThresholdContext:
    """Контекст настройки пороговых значений"""
    chat_id: int
    action: str  # 'set_threshold_group', 'set_threshold_device', etc.
    group_name: str
    device_id: str
    message_id: int
    timestamp: float
    
    def is_expired(self, timeout_seconds: int = 600) -> bool:  # 10 минут
        """Проверяет, истекло ли время контекста"""
        return time.time() - self.timestamp > timeout_seconds


class ThresholdContextManager:
    """Управление контекстами настройки пороговых значений"""
    
    def __init__(self):
        self._contexts: Dict[int, ThresholdContext] = {}
    
    def set_context(
        self,
        user_id: int,
        chat_id: int,
        action: str,
        group_name: str,
        device_id: str,
        message_id: int
    ) -> None:
        """
        Устанавливает контекст пороговых значений
        
        Args:
            user_id: ID пользователя
            chat_id: ID чата
            action: Тип действия
            group_name: Название группы
            device_id: ID устройства
            message_id: ID сообщения
        """
        self._contexts[user_id] = ThresholdContext(
            chat_id=chat_id,
            action=action,
            group_name=group_name,
            device_id=device_id,
            message_id=message_id,
            timestamp=time.time()
        )
    
    def get_context(self, user_id: int) -> Optional[ThresholdContext]:
        """
        Получает контекст пороговых значений
        
        Args:
            user_id: ID пользователя
            
        Returns:
            ThresholdContext или None
        """
        context = self._contexts.get(user_id)
        
        # Удаляем истекшие контексты
        if context and context.is_expired():
            self.clear_context(user_id)
            return None
            
        return context
    
    def has_context(self, user_id: int) -> bool:
        """
        Проверяет, есть ли активный контекст у пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если контекст существует
        """
        return self.get_context(user_id) is not None
    
    def clear_context(self, user_id: int) -> None:
        """Очищает контекст пользователя"""
        self._contexts.pop(user_id, None)
    
    def clear_expired_contexts(self) -> int:
        """
        Очищает все истекшие контексты
        
        Returns:
            Количество очищенных контекстов
        """
        expired_users = [
            user_id for user_id, context in self._contexts.items()
            if context.is_expired()
        ]
        
        for user_id in expired_users:
            self.clear_context(user_id)
        
        return len(expired_users)
    
    def get_active_contexts_count(self) -> int:
        """Возвращает количество активных контекстов"""
        return len(self._contexts)


# Глобальный экземпляр менеджера контекста пороговых значений
threshold_context_manager = ThresholdContextManager()