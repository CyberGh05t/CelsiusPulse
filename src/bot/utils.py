"""
Утилиты для работы с Telegram ботом
"""
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from typing import Optional, Union
# Избегаем циклического импорта - импорты внутри функций

# Импортируем новые менеджеры состояний
from src.core.menu_manager import menu_manager

def track_user_menu(user_id: int, chat_id: int, message_id: int, menu_type: str = "main", menu_context: dict = None):
    """
    Отслеживает активное меню пользователя с полным контекстом
    
    Args:
        user_id: ID пользователя
        chat_id: ID чата
        message_id: ID сообщения с меню
        menu_type: Тип меню (main, settings, thresholds, group_devices, device_threshold, registration, etc.)
        menu_context: Дополнительный контекст меню (группа, устройство, шаг регистрации, etc.)
    """
    menu_manager.track_menu(user_id, chat_id, message_id, menu_type, menu_context)

def get_last_user_menu(user_id: int) -> dict:
    """
    Получает информацию о последнем активном меню пользователя
    
    Returns:
        Словарь с информацией о меню или None
    """
    menu_state = menu_manager.get_menu(user_id)
    if not menu_state:
        return None
    
    return {
        'chat_id': menu_state.chat_id,
        'message_id': menu_state.message_id,
        'menu_type': menu_state.menu_type,
        'menu_context': menu_state.menu_context,
        'timestamp': menu_state.timestamp
    }

def get_active_menu_context(user_id: int) -> dict:
    """
    Получает контекст активного меню пользователя
    
    Returns:
        Контекст меню или пустой словарь
    """
    return menu_manager.get_menu_context(user_id)

def get_active_menu_type(user_id: int) -> str:
    """
    Получает тип активного меню пользователя
    
    Returns:
        Тип меню или 'unknown'
    """
    return menu_manager.get_menu_type(user_id)

def is_menu_type(user_id: int, expected_type: str) -> bool:
    """
    Проверяет, является ли активное меню пользователя указанным типом
    
    Args:
        user_id: ID пользователя
        expected_type: Ожидаемый тип меню
        
    Returns:
        True если активное меню соответствует типу
    """
    return menu_manager.is_menu_type(user_id, expected_type)


async def send_message_with_persistent_keyboard(
    update: Update, 
    text: str, 
    parse_mode: Optional[str] = 'Markdown',
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    force_quick_keyboard: bool = False,
    is_registration: bool = False
) -> bool:
    """
    Отправляет сообщение с постоянно отображаемой клавиатурой главного меню
    
    Args:
        update: Объект обновления Telegram
        text: Текст сообщения
        parse_mode: Режим парсинга (Markdown по умолчанию)
        reply_markup: Существующая клавиатура (будет дополнена кнопкой главного меню)
        force_quick_keyboard: Принудительно использовать быструю клавиатуру
        is_registration: True если пользователь в процессе регистрации
        
    Returns:
        True если сообщение отправлено успешно, False в случае ошибки
    """
    try:
        # Импорты внутри функции для избежания циклических зависимостей
        from .keyboards import get_quick_main_keyboard, get_persistent_keyboard
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Определяем какую клавиатуру использовать
        if force_quick_keyboard:
            keyboard = get_quick_main_keyboard()
        elif reply_markup:
            keyboard = get_persistent_keyboard(user_id, reply_markup, is_registration=is_registration)
        else:
            keyboard = get_persistent_keyboard(user_id, is_registration=is_registration)
        
        # Отправляем сообщение с клавиатурой
        sent_message = None
        if hasattr(update, 'callback_query') and update.callback_query:
            # Для callback query пытаемся сначала отредактировать сообщение
            try:
                await update.callback_query.edit_message_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode=parse_mode
                )
                # Отслеживаем отредактированное сообщение
                track_user_menu(user_id, chat_id, update.callback_query.message.message_id)
                return True
            except Exception:
                # Если не получилось отредактировать, отправляем новое
                sent_message = await update.callback_query.message.reply_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode=parse_mode
                )
        else:
            # Для обычных сообщений
            sent_message = await update.message.reply_text(
                text,
                reply_markup=keyboard,
                parse_mode=parse_mode
            )
        
        # Отслеживаем отправленное сообщение
        if sent_message:
            track_user_menu(user_id, chat_id, sent_message.message_id)
        return True
            
    except Exception as e:
        # В случае ошибки пытаемся отправить простое сообщение
        try:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.answer(text[:200], show_alert=True)
            else:
                await update.message.reply_text(f"⚠️ {text[:200]}")
            return False
        except:
            return False


async def reply_with_keyboard(
    update: Update,
    text: str,
    parse_mode: Optional[str] = 'Markdown',
    custom_keyboard: Optional[InlineKeyboardMarkup] = None,
    is_registration: bool = False
) -> bool:
    """
    Отвечает на сообщение с автоматическим добавлением кнопки главного меню
    
    Args:
        update: Объект обновления
        text: Текст ответа
        parse_mode: Режим парсинга
        custom_keyboard: Пользовательская клавиатура (будет дополнена)
        is_registration: True если пользователь в процессе регистрации
        
    Returns:
        True если успешно
    """
    return await send_message_with_persistent_keyboard(
        update, text, parse_mode, reply_markup=custom_keyboard, is_registration=is_registration
    )


async def safe_edit_with_keyboard(
    query,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = 'Markdown',
    menu_type: str = "main",
    menu_context: dict = None
) -> bool:
    """
    Безопасное редактирование сообщения с автоматическим отслеживанием контекста
    Расширенная версия с полным контекстным отслеживанием меню
    """
    try:
        # Импорты внутри функции для избежания циклических зависимостей
        from .keyboards import get_persistent_keyboard, get_quick_main_keyboard
        
        user_id = query.from_user.id
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        
        # Если клавиатуры нет, создаем с кнопкой главного меню
        if not reply_markup:
            reply_markup = get_persistent_keyboard(user_id)
        else:
            # Дополняем существующую клавиатуру кнопкой главного меню
            reply_markup = get_persistent_keyboard(user_id, reply_markup)
        
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        
        # Автоматически определяем тип меню по тексту и callback data, если не указан
        if menu_type == "main" and hasattr(query, 'data'):
            detected_type, detected_context = detect_menu_type_from_callback(query.data, text)
            if detected_type != "main":
                menu_type = detected_type
                if menu_context is None:
                    menu_context = detected_context
        
        # Отслеживаем отредактированное меню с полным контекстом
        track_user_menu(user_id, chat_id, message_id, menu_type, menu_context)
        return True
        
    except Exception as e:
        try:
            # Если редактирование не удалось, показываем только уведомление
            # НЕ создаем новое сообщение, чтобы избежать спама
            await query.answer("✅ Данные обновлены", show_alert=True)
            return False
        except:
            # Последняя попытка - тихое уведомление
            try:
                await query.answer("ℹ️ Обновлено")
            except:
                pass
            return False


def detect_menu_type_from_callback(callback_data: str, text: str) -> tuple:
    """
    Автоматически определяет тип меню по callback data и тексту
    
    Returns:
        Кортеж (menu_type, menu_context)
    """
    context = {}
    
    if callback_data.startswith("settings_thresholds"):
        return "thresholds", context
    elif callback_data.startswith("change_threshold_"):
        group_name = callback_data.replace("change_threshold_", "")
        context['group_name'] = group_name
        return "group_devices", context
    elif callback_data.startswith("set_threshold_"):
        parts = callback_data.split("_")
        if len(parts) >= 4:
            group_name = parts[2]
            device_id = "_".join(parts[3:])
            context['group_name'] = group_name
            context['device_id'] = device_id
        return "device_threshold", context
    elif callback_data.startswith("statistics") or "статистика" in text.lower():
        return "statistics", context
    elif callback_data.startswith("admin") or "администратор" in text.lower():
        return "admin_list", context
    elif callback_data.startswith("reg_") or "регистрация" in text.lower():
        if "ФИО" in text:
            context['step'] = 'fio'
        elif "должность" in text:
            context['step'] = 'position'
        return "registration", context
    elif callback_data.startswith("help") or callback_data == "help":
        return "help", context
    elif callback_data.startswith("select_group") or callback_data.startswith("group_") or "инфо" in text.lower():
        if callback_data.startswith("group_"):
            group_name = callback_data.replace("group_", "")
            context['group_name'] = group_name
            return "group_info", context
        return "info", context
    else:
        return "main", context


async def smart_update_current_menu(
    update: Update,
    user_id: int,
    error_message: str,
    content_type: str = "неподдерживаемый контент"
) -> bool:
    """
    Универсальная функция для умного обновления текущего активного меню
    с принудительным механизмом обновления для решения "Message is not modified"
    
    Args:
        update: Объект обновления Telegram
        user_id: ID пользователя
        error_message: Сообщение об ошибке для отображения
        content_type: Тип обнаруженного контента
        
    Returns:
        True если удалось обновить активное меню
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import time
    
    menu_info = get_last_user_menu(user_id)
    if not menu_info:
        # Логируем отсутствие активного меню для отладки
        from src.config.logging import SecureLogger
        logger = SecureLogger(__name__)
        active_count = menu_manager.get_active_users_count()
        logger.warning(f"Нет активного меню для пользователя {user_id}. Всего активных меню: {active_count}")
        return False
    
    menu_type = menu_info.get('menu_type', 'unknown')
    menu_context = menu_info.get('menu_context', {})
    chat_id = menu_info.get('chat_id')
    message_id = menu_info.get('message_id')
    
    if not chat_id or not message_id:
        return False
    
    bot = update.get_bot()
    
    try:
        # Генерируем контекстно-зависимое сообщение и клавиатуру
        response_text, keyboard = await generate_context_aware_response(
            menu_type, menu_context, error_message, content_type, user_id
        )
        
        # ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ: добавляем невидимую временную метку для уникальности
        # Используем Unicode символы нулевой ширины для создания уникального контента
        timestamp = str(int(time.time() * 1000))[-3:]  # Последние 3 цифры миллисекунд
        force_indicators = ["⠀", "⠁", "⠂", "⠃", "⠄", "⠅", "⠆", "⠇", "⠈", "⠉"]  # Braille невидимые символы
        force_char = force_indicators[int(timestamp[-1])]  # Выбираем символ по последней цифре
        
        # Добавляем невидимый символ в конец сообщения
        response_text += force_char
        
        # ВСЕГДА указываем reply_markup - если keyboard=None, создаем исходную клавиатуру
        if keyboard is None:
            # Создаем исходную клавиатуру для текущего типа меню
            keyboard = await recreate_original_keyboard(menu_type, menu_context, user_id)
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=response_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # Логируем успешное обновление
        from src.config.logging import SecureLogger
        logger = SecureLogger(__name__)
        logger.info(f"✅ Меню {menu_type} успешно обновлено для пользователя {user_id}")
        
        return True
        
    except Exception as e:
        error_msg = str(e).lower()
        
        # Если все еще получаем "message is not modified" - делаем дополнительную попытку
        if "message is not modified" in error_msg or "not modified" in error_msg:
            try:
                # Генерируем новую уникальную версию с дополнительным индикатором
                response_text, keyboard = await generate_context_aware_response(
                    menu_type, menu_context, error_message, content_type, user_id
                )
                
                # Добавляем дополнительный индикатор обновления
                update_time = time.strftime("%H:%M:%S", time.localtime())
                response_text += f"\n\n`⟨ обновлено {update_time} ⟩`"
                
                # Также учитываем случай с None клавиатурой
                if keyboard is None:
                    keyboard = await recreate_original_keyboard(menu_type, menu_context, user_id)
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=response_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                
                return True
                
            except Exception as e2:
                # Если и это не помогло - логируем обе ошибки
                from src.config.logging import SecureLogger
                logger = SecureLogger(__name__)
                logger.error(f"Критическая ошибка обновления меню {menu_type}: {e} → {e2}")
                return False
        else:
            # Другие типы ошибок
            from src.config.logging import SecureLogger
            logger = SecureLogger(__name__)
            logger.error(f"Ошибка при умном обновлении меню {menu_type}: {e}")
            return False


async def recreate_original_keyboard(menu_type: str, menu_context: dict, user_id: int):
    """
    Воссоздает исходную клавиатуру для указанного типа меню
    
    Args:
        menu_type: Тип меню (info, thresholds, help, etc.)
        menu_context: Контекст меню
        user_id: ID пользователя
        
    Returns:
        Клавиатура соответствующего типа меню
    """
    # Импортируем функции клавиатур
    from .keyboards import get_help_keyboard, get_main_keyboard
    from src.core.auth import get_user_role
    
    # Получаем роль пользователя
    role = get_user_role(user_id)
    
    if menu_type == "help":
        return get_help_keyboard()
    elif menu_type == "info":
        # Для меню инфо нужно получить группы
        from src.core.auth import get_user_accessible_groups
        groups = get_user_accessible_groups(user_id)
        from .keyboards import get_groups_keyboard
        return get_groups_keyboard(groups, show_all=True)
    elif menu_type == "thresholds":
        # Для меню пороговых значений
        from src.core.auth import get_user_accessible_groups
        groups = get_user_accessible_groups(user_id)
        from .keyboards import get_groups_keyboard
        # Создаем клавиатуру для выбора групп для настройки порогов
        keyboard = []
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        for i in range(0, len(groups), 2):
            row = []
            for j in range(2):
                if i + j < len(groups):
                    group = groups[i + j]
                    row.append(InlineKeyboardButton(
                        f"⚙️ {group}", 
                        callback_data=f"change_threshold_{group}"
                    ))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="back_to_main")])
        return InlineKeyboardMarkup(keyboard)
    elif menu_type == "group_devices":
        # Для списка устройств в группе
        group_name = menu_context.get('group_name', '')
        from src.core.storage import ThresholdManager
        thresholds = ThresholdManager.load_thresholds()
        devices = list(thresholds.get(group_name, {}).keys())
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = []
        for device_id in devices:
            keyboard.append([InlineKeyboardButton(
                f"🌡️ {device_id}", 
                callback_data=f"set_threshold_{group_name}_{device_id}"
            )])
        keyboard.append([
            InlineKeyboardButton("⬅️ Назад", callback_data="settings_thresholds"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")
        ])
        return InlineKeyboardMarkup(keyboard)
    elif menu_type == "device_threshold":
        # Для настройки конкретного устройства
        device_id = menu_context.get('device_id', '')
        group_name = menu_context.get('group_name', '')
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        # Проверяем тип установки порогов
        if group_name == 'USER' and device_id == 'ALL':
            # Для "Все мои группы" - возврат к меню пороговых значений
            keyboard = [
                [InlineKeyboardButton("🔙 Назад к группам", callback_data="settings_thresholds")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ]
        else:
            # Для конкретного устройства - возврат к группе
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад к группе", callback_data=f"change_threshold_{group_name}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ]
        return InlineKeyboardMarkup(keyboard)
    else:
        # По умолчанию возвращаем главное меню
        return get_main_keyboard(role)


async def generate_context_aware_response(
    menu_type: str,
    menu_context: dict,
    error_message: str,
    content_type: str,
    user_id: int
) -> tuple:
    """
    Генерирует контекстно-зависимое сообщение об ошибке БЕЗ изменения клавиатуры
    
    Returns:
        Кортеж (текст_ошибки, None) - клавиатура будет воссоздана автоматически!
    """
    
    if menu_type == "device_threshold":
        # Специальное сообщение для ввода пороговых значений
        device_id = menu_context.get('device_id', 'Устройство')
        group_name = menu_context.get('group_name', '')
        
        # Определяем тип установки порогов
        if group_name == 'USER' and device_id == 'ALL':
            # Установка порогов для всех групп пользователя
            if content_type in ["📝 произвольный текст", "❌ недопустимые символы"]:
                text = f"❌ **Неверный формат пороговых значений**\n\nДля установки порогов всем вашим датчикам введите значения в формате: `мин макс`\n\nПример: `18 25`"
            else:
                text = f"❌ **{error_message}**\n\nОбнаружен: {content_type}\n\nДля установки порогов используйте только текстовые сообщения."
        else:
            # Установка порогов для конкретного устройства
            if content_type in ["📝 произвольный текст", "❌ недопустимые символы"]:
                text = f"❌ **Неверный формат пороговых значений**\n\nДля устройства `{device_id}` введите пороги в формате: `мин макс`\n\nПример: `10 35`"
            else:
                text = f"❌ **{error_message}**\n\nОбнаружен: {content_type}\n\nДля установки порогов используйте только текстовые сообщения."
    
    elif menu_type == "registration":
        # Специальные сообщения для регистрации
        step = menu_context.get('step', 'unknown')
        if step == 'fio':
            text = f"❌ **{error_message}**\n\nОбнаружен: {content_type}\n\nДля регистрации введите ваше полное ФИО в формате: Фамилия Имя Отчество"
        elif step == 'position':
            text = f"❌ **{error_message}**\n\nОбнаружен: {content_type}\n\nВведите вашу должность (например: Директор, Заместитель директора)"
        else:
            text = f"❌ **{error_message}**\n\nОбнаружен: {content_type}\n\nПродолжите процесс регистрации."
    
    else:
        # Универсальное сообщение об ошибке для ВСЕХ остальных меню
        text = f"❌ **{error_message}**\n\nОбнаружен: {content_type}\n\nИспользуйте кнопки меню для навигации."
    
    # НЕ ВОЗВРАЩАЕМ КЛАВИАТУРУ - она будет воссоздана автоматически!
    return text, None