"""
Менеджер состояний регистрации - замена temp_storage
"""
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
import time


@dataclass
class RegistrationState:
    """Состояние процесса регистрации пользователя"""
    chat_id: int
    registration_step: str
    fio: Optional[str] = None
    position: Optional[str] = None
    selected_groups: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    
    def is_expired(self, timeout_seconds: int = 1800) -> bool:  # 30 минут
        """Проверяет, истекло ли время процесса регистрации"""
        return time.time() - self.timestamp > timeout_seconds
    
    def update_timestamp(self) -> None:
        """Обновляет временную метку последней активности"""
        self.timestamp = time.time()


class RegistrationManager:
    """Централизованное управление процессами регистрации"""
    
    def __init__(self):
        self._registration_states: Dict[int, RegistrationState] = {}
    
    def start_registration(self, chat_id: int) -> None:
        """
        Начинает процесс регистрации для пользователя
        
        Args:
            chat_id: ID чата пользователя
        """
        self._registration_states[chat_id] = RegistrationState(
            chat_id=chat_id,
            registration_step='fio'
        )
    
    def get_registration_state(self, chat_id: int) -> Optional[RegistrationState]:
        """
        Получает состояние регистрации пользователя
        
        Args:
            chat_id: ID чата пользователя
            
        Returns:
            RegistrationState или None если регистрация не найдена
        """
        state = self._registration_states.get(chat_id)
        
        # Удаляем истекшие регистрации
        if state and state.is_expired():
            self.clear_registration(chat_id)
            return None
            
        return state
    
    def is_in_registration(self, chat_id: int) -> bool:
        """
        Проверяет, находится ли пользователь в процессе регистрации
        
        Args:
            chat_id: ID чата пользователя
            
        Returns:
            True если пользователь в процессе регистрации
        """
        return self.get_registration_state(chat_id) is not None
    
    def get_registration_step(self, chat_id: int) -> Optional[str]:
        """
        Получает текущий шаг регистрации
        
        Args:
            chat_id: ID чата пользователя
            
        Returns:
            Название шага или None
        """
        state = self.get_registration_state(chat_id)
        return state.registration_step if state else None
    
    def update_fio(self, chat_id: int, fio: str) -> bool:
        """
        Обновляет ФИО и переводит на следующий шаг
        
        Args:
            chat_id: ID чата пользователя
            fio: ФИО пользователя
            
        Returns:
            True если обновление успешно
        """
        state = self.get_registration_state(chat_id)
        if not state or state.registration_step != 'fio':
            return False
        
        state.fio = fio
        state.registration_step = 'region'
        state.update_timestamp()
        return True
    
    def update_position(self, chat_id: int, position: str) -> bool:
        """
        Обновляет должность и завершает регистрацию
        
        Args:
            chat_id: ID чата пользователя
            position: Должность пользователя
            
        Returns:
            True если обновление успешно
        """
        state = self.get_registration_state(chat_id)
        if not state or state.registration_step != 'position':
            return False
        
        state.position = position
        state.registration_step = 'completed'
        state.update_timestamp()
        return True
    
    def toggle_group(self, chat_id: int, group: str) -> bool:
        """
        Переключает выбор группы (добавляет/убирает)
        
        Args:
            chat_id: ID чата пользователя
            group: Название группы
            
        Returns:
            True если группа была добавлена, False если убрана
        """
        state = self.get_registration_state(chat_id)
        if not state or state.registration_step != 'region':
            return False
        
        if group in state.selected_groups:
            state.selected_groups.remove(group)
            state.update_timestamp()
            return False
        else:
            state.selected_groups.append(group)
            state.update_timestamp()
            return True
    
    def finish_group_selection(self, chat_id: int) -> bool:
        """
        Завершает выбор групп и переходит к должности
        
        Args:
            chat_id: ID чата пользователя
            
        Returns:
            True если переход успешен
        """
        state = self.get_registration_state(chat_id)
        if not state or state.registration_step != 'region' or not state.selected_groups:
            return False
        
        state.registration_step = 'position'
        state.update_timestamp()
        return True
    
    def get_registration_data(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает все данные регистрации для сохранения
        
        Args:
            chat_id: ID чата пользователя
            
        Returns:
            Словарь с данными регистрации или None
        """
        state = self.get_registration_state(chat_id)
        if not state or state.registration_step != 'completed':
            return None
        
        return {
            'fio': state.fio,
            'position': state.position,
            'groups': state.selected_groups.copy(),
            'registration_timestamp': state.timestamp
        }
    
    def clear_registration(self, chat_id: int) -> None:
        """Очищает состояние регистрации пользователя"""
        self._registration_states.pop(chat_id, None)
    
    def clear_expired_registrations(self) -> int:
        """
        Очищает все истекшие процессы регистрации
        
        Returns:
            Количество очищенных регистраций
        """
        expired_chats = [
            chat_id for chat_id, state in self._registration_states.items()
            if state.is_expired()
        ]
        
        for chat_id in expired_chats:
            self.clear_registration(chat_id)
        
        return len(expired_chats)
    
    def get_active_registrations_count(self) -> int:
        """Возвращает количество активных процессов регистрации"""
        return len(self._registration_states)
    
    def get_registration_stats(self) -> Dict[str, int]:
        """
        Возвращает статистику по шагам регистрации
        
        Returns:
            Словарь {шаг: количество}
        """
        stats = {}
        for state in self._registration_states.values():
            step = state.registration_step
            stats[step] = stats.get(step, 0) + 1
        return stats


# Глобальный экземпляр менеджера регистрации
registration_manager = RegistrationManager()