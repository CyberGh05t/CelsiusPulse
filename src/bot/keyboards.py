"""
Модуль клавиатур для Telegram бота
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Optional


def get_main_keyboard(role: str) -> InlineKeyboardMarkup:
    """
    Создает основную клавиатуру в зависимости от роли пользователя
    
    Args:
        role: Роль пользователя ('admin', 'big_boss')
        
    Returns:
        Объект клавиатуры. Для незарегистрированных пользователей возвращает пустую клавиатуру.
    """
    # Незарегистрированные пользователи не имеют доступа к главному меню
    if role not in ['admin', 'big_boss']:
        return InlineKeyboardMarkup([])
    
    keyboard = []
    
    # Основные кнопки для всех зарегистрированных пользователей
    keyboard.append([
        InlineKeyboardButton("📊 Мои данные", callback_data="my_data"),
        InlineKeyboardButton("🌡️ Инфо", callback_data="select_group")
    ])
    
    keyboard.append([
        InlineKeyboardButton("⚙️ Пороговые значения", callback_data="settings_thresholds"),
        InlineKeyboardButton("📊 Статистика", callback_data="system_stats")
    ])
    
    # Дополнительные кнопки только для big boss
    if role == 'big_boss':
        keyboard.append([
            InlineKeyboardButton("👥 Список администраторов", callback_data="list_admins"),
            InlineKeyboardButton("🔐 Безопасность", callback_data="security_stats")
        ])
    
    # Кнопка помощи для всех зарегистрированных
    keyboard.append([
        InlineKeyboardButton("❓ Помощь", callback_data="help")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_groups_keyboard(available_groups: List[str], show_all: bool = False, selected_group: str = None) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с группами
    
    Args:
        available_groups: Список доступных групп
        show_all: Показывать ли кнопку "Все группы"
        selected_group: Выбранная группа для подсветки
        
    Returns:
        Объект клавиатуры
    """
    keyboard = []
    
    if not available_groups:
        keyboard.append([
            InlineKeyboardButton("⚠️ Нет доступных групп", callback_data="no_groups_temp")
        ])
    else:
        # Сортируем группы по алфавиту для стабильного порядка кнопок
        sorted_groups = sorted(available_groups)
        
        # Добавляем кнопки для каждой группы (по 3 в ряду)
        for i in range(0, len(sorted_groups), 3):
            row = []
            for j in range(3):
                if i + j < len(sorted_groups):
                    group = sorted_groups[i + j]
                    # Подсвечиваем выбранную группу
                    if selected_group and group == selected_group:
                        button_text = f"✅{group}"
                    else:
                        button_text = f"{group}"
                    
                    row.append(InlineKeyboardButton(
                        button_text, 
                        callback_data=f"group:{group}"
                    ))
            keyboard.append(row)
    
    # Дополнительные кнопки
    if show_all and available_groups:
        keyboard.append([
            InlineKeyboardButton("🌐 Все данные", callback_data="show_all_data")
        ])
    
    keyboard.append([
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_sensor_details_keyboard(device_id: str, group: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для детального просмотра датчика
    
    Args:
        device_id: ID датчика
        group: Группа датчика
        
    Returns:
        Объект клавиатуры
    """
    keyboard = [
        [
            InlineKeyboardButton("📊 Другие в группе", callback_data=f"group:{group}"),
            InlineKeyboardButton("🔄 Обновить", callback_data=f"sensor:{device_id}")
        ],
        [
            InlineKeyboardButton("⬅️ Назад к группам", callback_data="select_group")
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_help_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру помощи
    
    Returns:
        Объект клавиатуры
    """
    keyboard = [
        [
            InlineKeyboardButton("📖 Руководство пользователя", callback_data="help_manual"),
            InlineKeyboardButton("🔧 Техподдержка", callback_data="help_support")
        ],
        [
            InlineKeyboardButton("📞 Контакты", callback_data="help_contacts"),
            InlineKeyboardButton("❓ FAQ", callback_data="help_faq")
        ],
        [
            InlineKeyboardButton("📋 Пользовательское соглашение", callback_data="help_terms"),
            InlineKeyboardButton("📄 Лицензия", callback_data="help_license")
        ],
        [
            InlineKeyboardButton("🔍 CodeReview", callback_data="help_codereview"),
            InlineKeyboardButton("📊 Статус системы", callback_data="help_status")
        ],
        [
            InlineKeyboardButton("🔄 История изменений", callback_data="help_changelog"),
            InlineKeyboardButton("📺 Видеоинструкции", callback_data="help_videos")
        ],
        [
            InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main")
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_persistent_keyboard(user_id: int, current_keyboard: Optional[InlineKeyboardMarkup] = None, is_main_menu: bool = False, is_registration: bool = False) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой возврата в главное меню для постоянного отображения
    
    Args:
        user_id: ID пользователя
        current_keyboard: Существующая клавиатура (опционально)
        is_main_menu: True если это уже главное меню (не добавляем кнопку возврата)
        is_registration: True если пользователь в процессе регистрации (не добавляем кнопку главного меню)
        
    Returns:
        Клавиатура с кнопкой главного меню
    """
    from src.core.auth import get_user_role
    
    # Получаем роль пользователя
    role = get_user_role(user_id)
    
    # Если это главное меню, возвращаем без дополнительных кнопок
    if is_main_menu:
        if current_keyboard:
            return current_keyboard
        else:
            return get_main_keyboard(role)
    
    # Если пользователь в процессе регистрации, НЕ добавляем кнопку главного меню
    if is_registration:
        if current_keyboard:
            return current_keyboard
        else:
            # Возвращаем пустую клавиатуру для процесса регистрации
            return InlineKeyboardMarkup([])
    
    # Если пользователь не зарегистрирован (но НЕ в процессе регистрации), возвращаем простую клавиатуру с /start
    if role not in ['admin', 'big_boss']:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
        ])
    
    # Если есть текущая клавиатура, добавляем к ней кнопку главного меню
    if current_keyboard and current_keyboard.inline_keyboard:
        keyboard = []
        for row in current_keyboard.inline_keyboard:
            keyboard.append(row)
        
        # Проверяем, нет ли уже кнопки главного меню
        has_main_button = False
        for row in keyboard:
            for button in row:
                if button.callback_data == "back_to_main":
                    has_main_button = True
                    break
            if has_main_button:
                break
        
        # Добавляем кнопку главного меню если её нет
        if not has_main_button:
            keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")])
        
        return InlineKeyboardMarkup(keyboard)
    
    # Если клавиатуры нет, возвращаем полное главное меню
    return get_main_keyboard(role)


def get_quick_main_keyboard() -> InlineKeyboardMarkup:
    """
    Создает компактную клавиатуру с кнопкой возврата в главное меню
    Используется для ошибок и уведомлений
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ])


def get_registration_groups_keyboard(available_groups: List[str], selected_groups: List[str] = None) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с группами ТОЛЬКО для регистрации с множественным выбором
    
    Args:
        available_groups: Список доступных групп
        selected_groups: Список уже выбранных групп
        
    Returns:
        Объект клавиатуры
    """
    keyboard = []
    selected_groups = selected_groups or []
    
    if not available_groups:
        keyboard.append([
            InlineKeyboardButton("⚠️ Группы временно недоступны", callback_data="no_groups_registration")
        ])
    else:
        # Сортируем группы по алфавиту для стабильного порядка кнопок
        sorted_groups = sorted(available_groups)
        
        # Добавляем кнопки для каждой группы (по 3 в ряду)
        for i in range(0, len(sorted_groups), 3):
            row = []
            for j in range(3):
                if i + j < len(sorted_groups):
                    group = sorted_groups[i + j]
                    # Отмечаем выбранные группы галочкой
                    if group in selected_groups:
                        button_text = f"✅ {group}"
                    else:
                        button_text = f"{group}"
                    
                    row.append(InlineKeyboardButton(
                        button_text, 
                        callback_data=f"toggle_group:{group}"
                    ))
            keyboard.append(row)
        
        # Добавляем кнопку завершения выбора если есть выбранные группы
        if selected_groups:
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ Завершить выбор ({len(selected_groups)} групп)", 
                    callback_data="finish_group_selection"
                )
            ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    "⚠️ Выберите минимум одну группу", 
                    callback_data="need_select_group"
                )
            ])
    
    return InlineKeyboardMarkup(keyboard)


