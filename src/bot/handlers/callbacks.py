"""
Обработчики callback query (нажатий кнопок)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.config.logging import SecureLogger
from src.core.auth import get_user_role, is_authorized, can_access_group
from src.core.monitoring import get_all_groups, get_sensors_by_group, get_sensor_by_id, get_monitoring_statistics, get_user_statistics
from src.core.storage import AdminManager, ThresholdManager
from src.bot.messages import (
    format_group_sensors_message, format_sensor_message, 
    format_admin_list_message, format_thresholds_message,
    format_statistics_message, format_error_message
)
from src.bot.keyboards import (
    get_main_keyboard, get_groups_keyboard, get_sensor_details_keyboard,
    get_help_keyboard, get_quick_main_keyboard
)
from src.bot.utils import safe_edit_with_keyboard
from src.utils.security import validate_request_security, get_security_stats

logger = SecureLogger(__name__)

# Кеш для предотвращения повторных обращений
user_last_action = {}

# Функция safe_edit_with_keyboard заменена на safe_edit_with_keyboard из bot.utils
# для обеспечения постоянного отображения главного меню


def clear_threshold_context(user_id: int):
    """Очищает контекст пороговых значений для пользователя"""
    from src.core.threshold_context_manager import threshold_context_manager
    threshold_context_manager.clear_context(user_id)
    logger.info(f"Контекст пороговых значений очищен для пользователя {user_id}")


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Главный обработчик всех callback query (нажатий кнопок)
    """
    query = update.callback_query
    chat_id = update.effective_chat.id
    callback_data = query.data
    
    # Проверка безопасности
    is_safe, error_msg = validate_request_security(chat_id, callback_data)
    if not is_safe:
        await query.answer(error_msg)
        return
    
    # Проверка на спам (простой cooldown)
    from datetime import datetime, timedelta
    now = datetime.now()
    user_key = f"{chat_id}:{callback_data}"
    
    if user_key in user_last_action:
        time_diff = now - user_last_action[user_key]
        if time_diff < timedelta(seconds=1):  # 1 секунда cooldown
            await query.answer("⏳ Подождите немного перед следующим действием")
            return
    
    user_last_action[user_key] = now
    logger.info(f"Callback от {chat_id}: {callback_data}")
    
    try:
        # Безопасное подтверждение callback
        try:
            await query.answer()
        except Exception as e:
            logger.debug(f"Callback уже подтвержден или устарел: {e}")
        
        # Определяем роль пользователя
        role = get_user_role(chat_id)
        
        # Обработка различных callback действий
        if callback_data == "back_to_main":
            # Очищаем контекст пороговых значений при возврате в главное меню
            clear_threshold_context(query.from_user.id)
            await handle_main_menu(query, role)
        
        elif callback_data == "main_menu":
            # Обработка кнопки "Главное меню" из различных подменю
            clear_threshold_context(query.from_user.id)
            await handle_main_menu(query, role)
        
        elif callback_data == "my_data":
            # Проверяем, не находится ли пользователь в процессе регистрации
            if is_user_in_registration(chat_id):
                await query.answer("⚠️ Завершите сначала регистрацию", show_alert=True)
                return
            # Очищаем контекст пороговых значений при переходе к "Мои данные"
            clear_threshold_context(query.from_user.id)
            await handle_my_data(query, chat_id, role)
        
        elif callback_data == "select_group":
            if block_if_in_registration(chat_id):
                await query.answer("⚠️ Завершите сначала регистрацию", show_alert=True)
                return
            # Очищаем контекст пороговых значений при переходе к выбору групп
            clear_threshold_context(query.from_user.id)
            await handle_select_group(query, chat_id, role)
        
        elif callback_data.startswith("group:"):
            group_name = callback_data.split(":", 1)[1]
            
            # Проверяем, находится ли пользователь в процессе регистрации
            from src.bot.handlers.registration_handlers import registration_manager
            context = registration_manager.get_registration_data(chat_id) or {}
            if context.get('step') == 'groups':
                # В процессе регистрации - используем toggle для множественного выбора
                await handle_toggle_group(query, chat_id, group_name)
            else:
                # Обычный просмотр группы - очищаем контекст пороговых значений
                clear_threshold_context(query.from_user.id)
                await handle_group_data(query, chat_id, role, group_name)
        
        elif callback_data.startswith("toggle_group:"):
            group_name = callback_data.split(":", 1)[1]
            await handle_toggle_group(query, chat_id, group_name)
        
        elif callback_data == "finish_group_selection":
            await handle_finish_group_selection(query, chat_id)
        
        elif callback_data == "need_select_group":
            await query.answer("⚠️ Выберите минимум одну группу для продолжения", show_alert=True)
        
        elif callback_data == "no_groups_temp":
            await query.answer("⚠️ Нет доступных групп. Возможны проблемы с API или у вас нет доступа к группам из кеша.", show_alert=True)
        
        
        elif callback_data.startswith("sensor:"):
            sensor_id = callback_data.split(":", 1)[1]
            # Очищаем контекст пороговых значений при переходе к просмотру датчика
            clear_threshold_context(query.from_user.id)
            await handle_sensor_data(query, sensor_id)
        
        elif callback_data == "admin_all_data":
            if block_if_in_registration(chat_id):
                await query.answer("⚠️ Завершите сначала регистрацию", show_alert=True)
                return
            # Очищаем контекст пороговых значений при переходе к "Все данные"
            clear_threshold_context(query.from_user.id)
            await handle_admin_all_data(query, role)
        
        elif callback_data == "admin_thresholds":
            if block_if_in_registration(chat_id):
                await query.answer("⚠️ Завершите сначала регистрацию", show_alert=True)
                return
            # Очищаем контекст пороговых значений при переходе к "Просмотр порогов"
            clear_threshold_context(query.from_user.id)
            await handle_admin_thresholds(query, role)
            
        elif callback_data == "settings_thresholds":
            if block_if_in_registration(chat_id):
                await query.answer("⚠️ Завершите сначала регистрацию", show_alert=True)
                return
            # Очищаем контекст пороговых значений при возврате к меню выбора групп
            clear_threshold_context(query.from_user.id)
            await handle_settings_thresholds(query, role)
        
        elif callback_data == "list_admins":
            if block_if_in_registration(chat_id):
                await query.answer("⚠️ Завершите сначала регистрацию", show_alert=True)
                return
            # Очищаем контекст пороговых значений при переходе к "Список администраторов"
            clear_threshold_context(query.from_user.id)
            await handle_list_admins(query, role)
        
        elif callback_data == "system_stats":
            if block_if_in_registration(chat_id):
                await query.answer("⚠️ Завершите сначала регистрацию", show_alert=True)
                return
            # Очищаем контекст пороговых значений при переходе к "Статистика"
            clear_threshold_context(query.from_user.id)
            await handle_system_stats(query, role)
        
        elif callback_data == "security_stats":
            if block_if_in_registration(chat_id):
                await query.answer("⚠️ Завершите сначала регистрацию", show_alert=True)
                return
            # Очищаем контекст пороговых значений при переходе к "Безопасность"
            clear_threshold_context(query.from_user.id)
            await handle_security_stats(query, role)
        
        elif callback_data == "help":
            if block_if_in_registration(chat_id):
                await query.answer("⚠️ Завершите сначала регистрацию", show_alert=True)
                return
            # Очищаем контекст пороговых значений при переходе к "Помощь"
            clear_threshold_context(query.from_user.id)
            await handle_help(query)
        
        
        # Обработка изменения пороговых значений
        elif callback_data.startswith("change_threshold_"):
            group_name = callback_data[17:]  # Убираем "change_threshold_"
            if not can_access_group(chat_id, group_name):
                await query.answer("🚫 Доступ запрещен к группе: " + group_name, show_alert=True)
                return
            # Очищаем предыдущий контекст при переходе к другой группе
            clear_threshold_context(query.from_user.id)
            await handle_change_threshold_group(query, group_name, role)
        
        elif callback_data.startswith("set_threshold_"):
            # Format: set_threshold_GROUP_DEVICE
            # Специальная обработка для корректного парсинга device_id с подчеркиваниями
            remaining = callback_data[14:]  # Убираем "set_threshold_"
            
            # Специальные случаи
            if remaining == "ALL_ALL":
                group_name = "ALL"
                device_id = "ALL"
            elif remaining == "USER_ALL":
                group_name = "USER"
                device_id = "ALL"
            else:
                # Найдем первое подчеркивание - это разделитель группы и device_id
                first_underscore = remaining.find('_')
                if first_underscore != -1:
                    group_name = remaining[:first_underscore]
                    device_id = remaining[first_underscore + 1:]
                else:
                    # Fallback для некорректных данных
                    parts = remaining.split('_', 1)
                    if len(parts) >= 2:
                        group_name = parts[0]
                        device_id = parts[1]
                    else:
                        return
            
            # Специальные случаи для массовой установки порогов
            if group_name == "ALL" and device_id == "ALL":
                if role != 'big_boss':
                    await query.answer("🚫 Доступ запрещен: требуется роль Big Boss", show_alert=True)
                    return
                await handle_set_threshold_all_sensors(query, role)
                return
            elif group_name == "USER" and device_id == "ALL":
                # Установка порогов для всех датчиков пользователя (на основе доступных групп)
                await handle_set_threshold_user_sensors(query, role, chat_id)
                return
            
            if not can_access_group(chat_id, group_name):
                await query.answer("🚫 Доступ запрещен к группе: " + group_name, show_alert=True)
                return
            await handle_set_threshold_device(query, group_name, device_id, role)
        
        elif callback_data == "dummy":
            # Заглушка для декоративных кнопок
            await query.answer("🔹 Разделитель", show_alert=False)
        
        elif callback_data == "no_groups":
            await query.answer("❌ Нет доступных групп", show_alert=True)
        
        elif callback_data == "show_all_data":
            await handle_admin_all_data(query, role)
        
        elif callback_data.startswith("confirm_reg:"):
            await handle_confirm_registration_new(query, callback_data)
            
        elif callback_data.startswith("reject_reg:"):
            await handle_reject_registration_new(query, callback_data)
        
        elif callback_data in ["help_manual", "help_support", "help_contacts", "help_faq", 
                               "help_terms", "help_license", "help_codereview", "help_status",
                               "help_changelog", "help_videos"]:
            await handle_help_sections(query, callback_data)
        
        else:
            await query.edit_message_text("❓ Неизвестная команда")
    
    except Exception as e:
        logger.error(f"Ошибка в callback handler для {chat_id}: {e}")
        try:
            # Проверяем, что сообщение можно редактировать
            if query.message:
                await query.edit_message_text(
                    format_error_message('system_error', 'Ошибка при обработке запроса')
                )
            else:
                # Если нельзя редактировать, отправляем новое
                await query.answer("⚠️ Ошибка при обработке запроса", show_alert=True)
        except Exception as edit_error:
            logger.debug(f"Не удалось отредактировать сообщение: {edit_error}")
            # Последняя попытка - показать alert
            try:
                await query.answer("⚠️ Произошла ошибка", show_alert=True)
            except:
                pass  # Избегаем повторных ошибок


async def handle_main_menu(query, role: str):
    """Отображает главное меню"""
    from src.bot.utils import safe_edit_with_keyboard
    
    keyboard = get_main_keyboard(role)
    text = "🏠 Главное меню\n\nВыберите действие:"
    
    # Используем специальный параметр для главного меню
    try:
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception:
        # Если редактирование не удалось, отправляем новое сообщение
        await query.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        await query.answer("✅ Главное меню")


async def handle_my_data(query, chat_id: int, role: str):
    """Отображает данные пользователя"""
    # Получаем главное меню БЕЗ дополнительной кнопки возврата
    keyboard = get_main_keyboard(role)
    
    if role == 'big_boss':
        # Получаем информацию о big_boss
        admin_info = AdminManager.load_admin_info(chat_id)
        fio = admin_info.get('fio', 'Big Boss') if admin_info else 'Big Boss'
        # Для big_boss показываем общую информацию и статистику
        all_groups = get_all_groups()
        total_sensors = sum(len(get_sensors_by_group(group)) for group in all_groups)
        
        message = f"👤 Ваши данные\n\n"
        message += f"👨‍💼 ФИО: {fio}\n"
        message += f"🆔 Chat ID: `{chat_id}`\n"
        message += f"💼 Роль: Big Boss (полный доступ)\n"
        message += f"🌐 Доступ: ко всем группам системы\n\n"
                
    elif role == 'admin':
        # Для админов берем группы ТОЛЬКО из .env (ADMIN_GROUPS)
        from src.core.auth import ADMIN_GROUPS
        groups = ADMIN_GROUPS.get(chat_id, [])
        
        # Справочная информация из admins.json
        admin_info = AdminManager.load_admin_info(chat_id)
        fio = admin_info.get('fio', 'Не указано') if admin_info else 'Не указано'
        position = admin_info.get('position', 'Не указана') if admin_info else 'Не указана'
        
        message = f"👤 Ваши данные\n\n"
        message += f"👨‍💼 ФИО: {fio}\n"
        message += f"🆔 Chat ID: `{chat_id}`\n"
        message += f"💼 Должность: {position}\n"
        message += f"🔐 Роль: Администратор\n"
        message += f"📋 Назначенные группы: {', '.join(groups) if groups else 'Нет назначенных групп'}"
    
    else:
        # Для незарегистрированных пользователей
        message = f"👤 Ваши данные\n\n"
        message += f"🆔 Chat ID: `{chat_id}`\n"
        message += f"💼 Роль: Не зарегистрирован\n\n"
        message += "⚠️ Вы не зарегистрированы в системе.\n"
        message += "Нажмите /start для регистрации."
    
    # Используем прямой вызов чтобы НЕ добавлять дополнительную кнопку "Главное меню"
    try:
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')
    except Exception:
        # "Мои данные" статичны, при повторном нажатии молча игнорируем ошибку идентичного контента
        pass


async def handle_select_group(query, chat_id: int, role: str):
    """Отображает список доступных групп с правильной фильтрацией по ролям"""
    from src.core.auth import get_user_accessible_groups
    
    # Получаем ВСЕ группы из кеша (без фильтрации)
    all_cached_groups = get_all_groups()
    
    # Получаем группы, доступные конкретному пользователю (с фильтрацией по роли)
    user_accessible_groups = get_user_accessible_groups(chat_id)
    
    # Пересечение: показываем только те группы, которые есть в кеше И доступны пользователю
    if role == 'big_boss':
        # Big boss видит все группы из кеша
        available_groups = all_cached_groups
        logger.debug(f"BigBoss {chat_id}: показываем все {len(available_groups)} групп из кеша")
    else:
        # Админы видят только пересечение своих групп с группами из кеша
        available_groups = [g for g in all_cached_groups if g in user_accessible_groups]
        logger.debug(f"Админ {chat_id}: доступно {len(user_accessible_groups)} групп, "
                    f"в кеше {len(all_cached_groups)} групп, показываем {len(available_groups)} групп")
        
        if not available_groups and all_cached_groups and user_accessible_groups:
            logger.warning(f"Админ {chat_id} не имеет доступа ни к одной группе из кеша. "
                          f"Кеш: {all_cached_groups}, доступные: {user_accessible_groups}")
    
    # Логирование проблем с API
    if not all_cached_groups:
        logger.warning(f"API недоступен для пользователя {chat_id} (роль: {role}). "
                      f"Кеш пуст или устарел (старше 1 часа).")
    
    keyboard = get_groups_keyboard(available_groups, show_all=(role in ['admin', 'big_boss']))
    text = "📊 Выберите группу для просмотра:"
    
    await safe_edit_with_keyboard(
        query, 
        text, 
        reply_markup=keyboard,
        menu_type="info",
        menu_context={}
    )


async def handle_group_data(query, chat_id: int, role: str, group_name: str):
    """Отображает данные конкретной группы"""
    # Проверяем права доступа к группе
    if not can_access_group(chat_id, group_name):
        await query.edit_message_text(
            format_error_message('access_denied', f'Нет доступа к группе {group_name}')
        )
        return
    
    sensors = get_sensors_by_group(group_name)
    message = format_group_sensors_message(group_name, sensors)
    
    from src.core.auth import get_user_accessible_groups
    user_groups = get_user_accessible_groups(query.from_user.id)
    keyboard = get_groups_keyboard(user_groups, show_all=(role in ['admin', 'big_boss']), selected_group=group_name)
    
    await safe_edit_with_keyboard(query, message, reply_markup=keyboard, parse_mode=None)


async def handle_sensor_data(query, sensor_id: str):
    """Отображает данные конкретного датчика"""
    sensor = get_sensor_by_id(sensor_id)
    
    if not sensor:
        await query.edit_message_text(
            format_error_message('data_not_found', f'Датчик {sensor_id} не найден')
        )
        return
    
    message = format_sensor_message(sensor)
    keyboard = get_sensor_details_keyboard(sensor_id, sensor['group'])
    
    await safe_edit_with_keyboard(query, message, reply_markup=keyboard)


async def handle_admin_all_data(query, role: str):
    """Отображает все данные (с учетом прав доступа)"""
    if not is_authorized(query.from_user.id, 'admin'):
        await query.edit_message_text(
            format_error_message('access_denied')
        )
        return
    
    from src.core.auth import get_user_accessible_groups
    
    # Получаем группы, доступные пользователю
    user_groups = get_user_accessible_groups(query.from_user.id)
    total_sensors = 0
    
    if role == "big_boss":
        message = "📊 Все данные системы (BigBoss)\n\n"
    else:
        message = "📊 Данные ваших групп\n\n"
    
    for group in user_groups:
        sensors = get_sensors_by_group(group)
        total_sensors += len(sensors)
        message += f"📍 {group}: {len(sensors)} датчиков\n"
    
    if not user_groups:
        message += "❌ Нет доступных групп\n"
    else:
        message += f"\n📈 Итого: {total_sensors} датчиков в {len(user_groups)} группах"
    
    # Возвращаемся к меню выбора групп вместо главного меню
    keyboard = get_groups_keyboard(user_groups, show_all=(role in ['admin', 'big_boss']))
    
    await safe_edit_with_keyboard(query, message, reply_markup=keyboard)


async def handle_admin_thresholds(query, role: str):
    """Отображает пороговые значения (с учетом прав доступа)"""
    if not is_authorized(query.from_user.id, 'admin'):
        await query.edit_message_text(
            format_error_message('access_denied')
        )
        return
    
    from src.core.auth import get_user_accessible_groups
    
    # Получаем все пороги
    all_thresholds = ThresholdManager.load_thresholds()
    
    # Фильтруем по группам пользователя
    user_groups = get_user_accessible_groups(query.from_user.id)
    user_thresholds = {}
    
    for group in user_groups:
        if group in all_thresholds:
            user_thresholds[group] = all_thresholds[group]
    
    if role == "big_boss":
        message = "📊 Все пороговые значения (BigBoss)\n\n" + format_thresholds_message(all_thresholds)
    else:
        message = "📊 Пороговые значения ваших групп\n\n" + format_thresholds_message(user_thresholds)
    
    keyboard = get_main_keyboard(role)
    
    await safe_edit_with_keyboard(query, message, reply_markup=keyboard)


async def handle_list_admins(query, role: str):
    """Отображает список администраторов (только для big_boss)"""
    if not is_authorized(query.from_user.id, 'big_boss'):
        await query.edit_message_text(
            format_error_message('access_denied')
        )
        return
    
    admins = AdminManager.get_all_admins()
    message = format_admin_list_message(admins)
    
    # Добавляем время обновления для обеспечения обновления при повторном нажатии
    from datetime import datetime
    message += f"\n\n⏰ Обновлено: {datetime.now().strftime('%H:%M:%S')}"
    
    # Список администраторов с главным меню (как статистика)  
    keyboard = get_main_keyboard(role)
    await query.edit_message_text(message, reply_markup=keyboard)


async def handle_system_stats(query, role: str):
    """Отображает системную статистику с учетом прав доступа пользователя"""
    if not is_authorized(query.from_user.id, 'admin'):
        await query.edit_message_text(
            format_error_message('access_denied')
        )
        return
    
    # Используем новую функцию, которая фильтрует данные по правам доступа
    stats = get_user_statistics(query.from_user.id)
    message = format_statistics_message(stats)
    
    keyboard = get_main_keyboard(role)
    
    # Используем прямой вызов чтобы НЕ добавлять дополнительную кнопку "Главное меню"
    await query.edit_message_text(message, reply_markup=keyboard)


async def handle_security_stats(query, role: str):
    """Отображает статистику безопасности (только для big_boss)"""
    if not is_authorized(query.from_user.id, 'big_boss'):
        await query.edit_message_text(
            format_error_message('access_denied')
        )
        return
    
    security_stats = get_security_stats()
    
    message = (
        "🔐 Статистика безопасности\n\n"
        f"👥 Активных пользователей: {security_stats.get('active_users', 0)}\n"
        f"🚫 Заблокированных: {security_stats.get('blocked_users', 0)}\n"
        f"⚠️ Подозрительных: {security_stats.get('suspicious_users', 0)}\n"
        f"🔍 Всего инцидентов: {security_stats.get('total_suspicious_incidents', 0)}"
    )
    
    # Добавляем время обновления для обеспечения обновления при повторном нажатии
    from datetime import datetime
    message += f"\n\n⏰ Обновлено: {datetime.now().strftime('%H:%M:%S')}"
    
    # Статистика безопасности с главным меню (как статистика)
    keyboard = get_main_keyboard(role)
    await query.edit_message_text(message, reply_markup=keyboard)


async def handle_help(query):
    """Отображает справку"""
    from src.bot.utils import safe_edit_with_keyboard
    keyboard = get_help_keyboard()
    
    help_text = """
❓ Справка по системе

🌡️ CelsiusPulse Bot - система мониторинга температуры складских помещений.

Основные функции:
• Просмотр текущих данных температуры
• Мониторинг по группам помещений
• Автоматические уведомления о критических значениях

Навигация:
Используйте кнопки для перемещения по меню.
    """
    
    await safe_edit_with_keyboard(
        query, 
        help_text, 
        reply_markup=keyboard,
        parse_mode='Markdown',
        menu_type="help",
        menu_context={}
    )




async def handle_region_selection(query, chat_id: int, region: str):
    """Обработка выбора региона при регистрации"""
    from src.bot.handlers.admin import handle_user_registration, validate_registration_context
    from src.core.monitoring import get_all_groups
    
    # Получаем контекст из временного хранилища
    if not hasattr(handle_user_registration, 'temp_storage'):
        handle_user_registration.temp_storage = {}
        
    context = handle_user_registration.temp_storage.get(chat_id, {})
    
    # ВАЛИДАЦИЯ: Проверяем состояние регистрации
    if not validate_registration_context(context, 'region'):
        await query.edit_message_text(
            "❌ Ошибка в процессе регистрации\n\n"
            "Состояние регистрации повреждено.\n"
            "Начните заново с команды /start",
            parse_mode='Markdown'
        )
        # Очищаем поврежденные данные
        handle_user_registration.temp_storage.pop(chat_id, None)
        return
    
    # ВАЛИДАЦИЯ: Проверяем, что выбранная группа существует
    available_groups = get_all_groups()
    if region not in available_groups:
        await query.edit_message_text(
            "❌ Неверный регион\n\n"
            f"Регион '{region}' не существует.\n"
            "Начните регистрацию заново с команды /start",
            parse_mode='Markdown'
        )
        handle_user_registration.temp_storage.pop(chat_id, None)
        return
    
    context['region'] = region
    context['registration_step'] = 'position'
    handle_user_registration.temp_storage[chat_id] = context
    
    await query.edit_message_text(
        f"✅ Регион выбран: {region}\n\n"
        "💼 Введите должность:",
        parse_mode='Markdown'
    )


def is_user_in_registration(chat_id: int) -> bool:
    """
    Проверяет, находится ли пользователь в процессе регистрации
    """
    from src.bot.handlers.admin import handle_user_registration
    
    if not hasattr(handle_user_registration, 'temp_storage'):
        return False
    
    context = handle_user_registration.temp_storage.get(chat_id, {})
    return bool(context.get('registration_step'))


def block_if_in_registration(chat_id: int) -> bool:
    """
    Блокирует действие если пользователь в процессе регистрации
    Возвращает True если нужно заблокировать
    """
    return is_user_in_registration(chat_id)


def registration_guard(func):
    """Декоратор для блокировки действий во время регистрации"""
    async def wrapper(query, *args, **kwargs):
        chat_id = query.from_user.id
        if block_if_in_registration(chat_id):
            await query.answer("⚠️ Завершите сначала регистрацию", show_alert=True)
            return
        return await func(query, *args, **kwargs)
    return wrapper


async def handle_toggle_group(query, chat_id: int, group_name: str):
    """Обработка переключения выбора группы"""
    from src.core.registration_manager import registration_manager
    from src.bot.handlers.registration_handlers import RegistrationHandler
    
    # Проверяем, что пользователь в процессе регистрации
    if not registration_manager.is_in_registration(chat_id):
        await query.answer("❌ Ошибка: пользователь не в процессе регистрации", show_alert=True)
        return
    
    # Проверяем текущий шаг регистрации
    step = registration_manager.get_registration_step(chat_id)
    if step != 'region':
        await query.answer(f"❌ Ошибка: неверный шаг регистрации (текущий: {step})", show_alert=True)
        return
    
    # Переключаем группу напрямую через registration_manager
    is_added = registration_manager.toggle_group(chat_id, group_name)
    
    # Получаем обновленное состояние
    state = registration_manager.get_registration_state(chat_id)
    from src.core.monitoring import get_all_groups
    from src.bot.keyboards import get_registration_groups_keyboard
    
    available_groups = get_all_groups()
    keyboard = get_registration_groups_keyboard(available_groups, state.selected_groups)
    
    groups_text = (
        f"✅ **ФИО сохранено:** `{state.fio}`\n\n"
        "🔹 **Шаг 2/3: Выберите ваши рабочие группы**\n\n"
        "📋 **Доступные группы:**\n"
        f"• Всего в системе: {len(available_groups)} групп\n"
        f"• Выбрано: {len(state.selected_groups)} групп\n\n"
        "💡 **Инструкция:**\n"
        "• Нажмите на группы, к которым у вас есть доступ\n"
        "• Можно выбрать несколько групп\n"
        "• Выбранные группы отмечены ✅\n"
        "• После выбора нажмите **Завершить выбор**"
    )
    
    # Обновляем сообщение
    try:
        await query.edit_message_text(
            groups_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ошибка обновления меню выбора групп: {e}")
    
    # Показываем уведомление
    action = "добавлена" if is_added else "убрана"
    await query.answer(f"Группа {group_name} {action}", show_alert=False)


async def handle_finish_group_selection(query, chat_id: int):
    """Завершение выбора групп и переход к вводу должности"""
    from src.core.registration_manager import registration_manager
    from src.bot.handlers.registration_handlers import RegistrationHandler
    
    # Проверяем, что группы выбраны
    state = registration_manager.get_registration_state(chat_id)
    
    if not state or not state.selected_groups:
        await query.answer("❌ Выберите минимум одну группу", show_alert=True)
        return
    
    # Переходим к следующему шагу
    if registration_manager.finish_group_selection(chat_id):
        position_text = (
            f"✅ **ФИО:** `{state.fio}`\n"
            f"✅ **Группы:** {', '.join(state.selected_groups)}\n\n"
            "🔹 **Шаг 3/3: Введите вашу должность**\n\n"
            "📋 **Требования:**\n"
            "• Минимум 2 символа\n"
            "• Укажите реальную должность\n\n"
            "📝 **Примеры:**\n"
            "• `Директор`\n"
            "• `Заместитель директора`\n"
            "• `Региональный руководитель`\n"
            "• `Старший смены`\n"
            "• `Бригадир`"
        )
        
        await query.edit_message_text(
            position_text,
            parse_mode='Markdown'
        )
    else:
        await query.answer("❌ Ошибка при переходе к следующему шагу", show_alert=True)


# Функции для работы с пороговыми значениями

async def handle_settings_thresholds(query, role: str):
    """Показывает меню выбора группы для изменения пороговых значений"""
    from src.core.auth import get_user_accessible_groups
    
    user_groups = get_user_accessible_groups(query.from_user.id)
    
    if not user_groups:
        await query.edit_message_text("❌ У вас нет доступа к группам")
        return
    
    keyboard = []
    
    # Добавляем кнопку для установки порогов всем датчикам пользователя
    # Для админов - только если у них больше одной группы, для big_boss - всегда
    if role == "big_boss":
        keyboard.append([
            InlineKeyboardButton("🌍 Все датчики системы", callback_data="set_threshold_ALL_ALL"),
            InlineKeyboardButton("🔧 Мои группы", callback_data="set_threshold_USER_ALL")
        ])
        keyboard.append([InlineKeyboardButton("➖➖➖", callback_data="dummy")])
    elif role == "admin" and len(user_groups) > 1:
        keyboard.append([
            InlineKeyboardButton("🔧 Все мои группы", callback_data="set_threshold_USER_ALL")
        ])
        keyboard.append([InlineKeyboardButton("➖➖➖", callback_data="dummy")])
    
    # Группы располагаем в 3 ряда
    for i in range(0, len(user_groups), 3):
        row = []
        for j in range(3):
            if i + j < len(user_groups):
                group = user_groups[i + j]
                row.append(InlineKeyboardButton(f"🔧 {group}", callback_data=f"change_threshold_{group}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if role == "big_boss":
        message = "⚙️ Изменение пороговых значений (BigBoss)\n\nВыберите группу или все датчики:"
    else:
        if len(user_groups) > 1:
            message = "⚙️ Изменение пороговых значений\n\nВыберите группу или все ваши группы:"
        else:
            message = "⚙️ Изменение пороговых значений\n\nВыберите вашу группу:"
    
    await safe_edit_with_keyboard(
        query, 
        message, 
        reply_markup=reply_markup,
        menu_type="thresholds",
        menu_context={}
    )


async def handle_change_threshold_group(query, group_name: str, role: str):
    """Показывает устройства группы для изменения пороговых значений"""
    sensors = get_sensors_by_group(group_name)
    
    if not sensors:
        await query.edit_message_text(f"❌ Нет датчиков в группе {group_name}")
        return
    
    keyboard = []
    
    # Кнопка для установки общих пороговых значений для всей группы
    keyboard.append([
        InlineKeyboardButton(f"🔧 Вся группа {group_name}", callback_data=f"set_threshold_{group_name}_ALL")
    ])
    
    keyboard.append([InlineKeyboardButton("➖➖➖", callback_data="dummy")])
    
    # Кнопки для каждого устройства - располагаем в 3 ряда
    for i in range(0, min(len(sensors), 10), 3):  # Ограничиваем до 10 устройств
        row = []
        for j in range(3):
            if i + j < min(len(sensors), 10):
                sensor = sensors[i + j]
                device_id = sensor['device_id']
                temp = sensor.get('temperature', 'N/A')
                row.append(InlineKeyboardButton(
                    f"{device_id} ({temp}°C)",
                    callback_data=f"set_threshold_{group_name}_{device_id}"
                ))
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton("🔙 Назад к группам", callback_data="settings_thresholds")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"🌡️ Группа {group_name}\n\n"
    message += f"Найдено датчиков: {len(sensors)}\n"
    message += "Выберите устройство или установите общие значения:"
    
    await safe_edit_with_keyboard(
        query, 
        message, 
        reply_markup=reply_markup,
        menu_type="group_devices",
        menu_context={"group_name": group_name}
    )


async def handle_set_threshold_device(query, group_name: str, device_id: str, role: str):
    """Показывает текущие пороги и предлагает их изменить"""
    from src.core.storage import ThresholdManager
    from src.core.threshold_context_manager import threshold_context_manager
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"handle_set_threshold_device: group_name='{group_name}', device_id='{device_id}'")
    
    current_thresholds = ThresholdManager.load_thresholds()
    current = current_thresholds.get(group_name, {}).get(device_id, {"min": 18.0, "max": 25.0})
    
    if device_id == "ALL":
        message = f"⚙️ Пороговые значения для всей группы {group_name}\n\n"
        message += f"🌡️ Минимум: {current['min']}°C\n"
        message += f"🌡️ Максимум: {current['max']}°C\n\n"
        message += "📝 Отправьте новые значения в формате:\n"
        message += "`мин макс`\n"
        message += "Например: `18 25`"
        
        # Сохраняем контекст через новую систему
        threshold_context_manager.set_context(
            user_id=query.from_user.id,
            chat_id=query.message.chat_id,
            action='set_threshold_group',
            group_name=group_name,
            device_id=device_id,
            message_id=query.message.message_id
        )
        
    else:
        # Получаем текущую температуру устройства
        sensor = get_sensor_by_id(device_id)
        current_temp = sensor.get('temperature', 'N/A') if sensor else 'N/A'
        
        # Экранируем подчеркивания в device_id для корректного отображения в Markdown
        safe_device_id = device_id.replace('_', '\\_')
        
        message = f"⚙️ Устройство {safe_device_id}\n"
        message += f"🏢 Группа: {group_name}\n"
        message += f"🌡️ Текущая температура: {current_temp}°C\n\n"
        message += f"Текущие пороги:\n"
        message += f"🌡️ Минимум: {current['min']}°C\n"
        message += f"🌡️ Максимум: {current['max']}°C\n\n"
        message += "📝 Отправьте новые значения в формате:\n"
        message += "`мин макс`\n"
        message += "Например: `18 25`"
        
        # Сохраняем контекст через новую систему
        threshold_context_manager.set_context(
            user_id=query.from_user.id,
            chat_id=query.message.chat_id,
            action='set_threshold_device',
            group_name=group_name,
            device_id=device_id,
            message_id=query.message.message_id
        )
    
    # Определяем правильную кнопку "Назад" в зависимости от контекста
    if group_name in ['ALL', 'USER']:
        # Для массовых операций - возврат к выбору групп
        back_text = "🔙 Назад к группам"
        back_callback = "settings_thresholds"
    else:
        # Для обычных групп - возврат к устройствам группы
        back_text = "🔙 Назад к устройствам"
        back_callback = f"change_threshold_{group_name}"
    
    keyboard = [[
        InlineKeyboardButton(back_text, callback_data=back_callback)
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Для KRR логируем полное сообщение для отладки
    if group_name == "KRR":
        logger.info(f"KRR message length: {len(message)} chars")
        logger.info(f"KRR message content: {message}")
        logger.info(f"KRR callback_data: change_threshold_{group_name}")
    
    try:
        await safe_edit_with_keyboard(
            query, 
            message, 
            reply_markup=reply_markup,
            menu_type="device_threshold",
            menu_context={"group_name": group_name, "device_id": device_id}
        )
        logger.info(f"Successfully edited threshold message for {group_name}:{device_id}")
    except Exception as e:
        logger.error(f"Error editing threshold message for {group_name}:{device_id}: {e}")
        # Попробуем отправить новое сообщение
        try:
            await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e2:
            logger.error(f"Error sending new threshold message for {group_name}:{device_id}: {e2}")
            await query.answer("❌ Ошибка при отображении порогов", show_alert=True)


async def handle_set_threshold_all_sensors(query, role: str):
    """Установка пороговых значений для ВСЕХ датчиков всех групп (только для big_boss)"""
    from src.core.storage import ThresholdManager
    from src.core.monitoring import get_all_groups, get_sensors_by_group
    from src.core.threshold_context_manager import threshold_context_manager
    
    # Получаем общее количество датчиков
    all_groups = get_all_groups()
    total_sensors = sum(len(get_sensors_by_group(group)) for group in all_groups)
    
    message = f"🌍 **Установка порогов для ВСЕХ датчиков**\n\n"
    message += f"📍 Всего групп: {len(all_groups)}\n"
    message += f"🌡️ Всего датчиков: {total_sensors}\n\n"
    message += f"⚠️ **ВНИМАНИЕ!** Это изменит пороговые значения для ВСЕХ {total_sensors} датчиков во ВСЕХ группах системы!\n\n"
    message += f"📝 Отправьте новые значения в формате:\n"
    message += f"`мин макс`\n"
    message += f"Например: `18 25`"
    
    # Сохраняем контекст через новую систему
    threshold_context_manager.set_context(
        user_id=query.from_user.id,
        chat_id=query.message.chat_id,
        action='set_threshold_all_sensors',
        group_name='ALL',
        device_id='ALL',
        message_id=query.message.message_id
    )
    
    keyboard = [[
        InlineKeyboardButton("🔙 Назад к группам", callback_data="settings_thresholds")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_with_keyboard(query, message, reply_markup=reply_markup)


async def handle_set_threshold_user_sensors(query, role: str, chat_id: int):
    """Установка пороговых значений для ВСЕХ датчиков доступных пользователю групп"""
    from src.core.storage import ThresholdManager
    from src.core.monitoring import get_sensors_by_group
    from src.core.auth import get_user_accessible_groups
    
    # Получаем группы доступные пользователю
    user_groups = get_user_accessible_groups(chat_id)
    if not user_groups:
        await query.edit_message_text("❌ У вас нет доступа к группам")
        return
    
    # Получаем общее количество датчиков в доступных группах
    total_sensors = sum(len(get_sensors_by_group(group)) for group in user_groups)
    
    message = f"🔧 **Установка порогов для всех ваших датчиков**\n\n"
    message += f"📍 Ваши группы: {', '.join(user_groups)}\n"
    message += f"🌡️ Всего датчиков: {total_sensors}\n\n"
    message += f"⚠️ **ВНИМАНИЕ!** Это изменит пороговые значения для ВСЕХ {total_sensors} датчиков в ваших {len(user_groups)} группах!\n\n"
    message += f"📝 Отправьте новые значения в формате:\n"
    message += f"`мин макс`\n"
    message += f"Например: `18 25`"
    
    # Сохраняем контекст для обработки ввода через новую систему
    from src.core.threshold_context_manager import threshold_context_manager
    
    threshold_context_manager.set_context(
        user_id=query.from_user.id,
        chat_id=chat_id,
        action='set_threshold_user_sensors', 
        group_name='USER',
        device_id='ALL',
        message_id=query.message.message_id
    )
    
    keyboard = [[
        InlineKeyboardButton("🔙 Назад к группам", callback_data="settings_thresholds"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_with_keyboard(
        query, 
        message, 
        reply_markup=reply_markup,
        menu_type="device_threshold",
        menu_context={
            'group_name': 'USER',
            'device_id': 'ALL'
        }
    )


async def handle_confirm_registration_new(query, callback_data: str):
    """Новый обработчик подтверждения регистрации с коротким ID"""
    from src.bot.handlers.admin import get_pending_registration, remove_pending_registration
    
    registration_id = callback_data.split(":")[1]
    registration_data = get_pending_registration(registration_id)
    
    if not registration_data:
        await query.answer("❌ Данные регистрации не найдены", show_alert=True)
        return
        
    user_chat_id = registration_data['chat_id']
    fio = registration_data['fio']
    groups = registration_data['groups']
    position = registration_data['position']
    
    logger.info(f"Подтверждение регистрации для {user_chat_id} в группах {groups}")
    
    try:
        # Обновляем ADMIN_GROUPS в памяти и .env файле
        from src.core.auth import update_env_file
        
        # Сначала обновляем глобальные переменные в памяти
        import src.core.auth as auth_module
        if user_chat_id not in auth_module.ADMIN_GROUPS:
            auth_module.ADMIN_GROUPS[user_chat_id] = []
        
        # Добавляем все выбранные группы
        for group in groups:
            if group and group not in auth_module.ADMIN_GROUPS[user_chat_id]:
                auth_module.ADMIN_GROUPS[user_chat_id].append(group)
            
        # Обновляем .env файл
        update_env_file()
        
        # Сохраняем данные администратора в admins.json
        from src.core.storage import AdminManager
        
        # Извлекаем nickname если есть
        try:
            user = await query.get_bot().get_chat(user_chat_id)
            nickname = user.username or ""
        except Exception:
            nickname = ""
            
        AdminManager.save_admin({
            'chat_id': user_chat_id,
            'fio': fio,
            'nickname': nickname,
            'groups': groups,
            'position': position,
            'registered_at': query.message.date.isoformat()
        })
        
        # Уведомляем пользователя
        from src.core.auth import get_user_role
        user_role = get_user_role(user_chat_id)
        groups_text = ', '.join(groups)
        await query.get_bot().send_message(
            chat_id=user_chat_id,
            text=f"✅ Ваша регистрация подтверждена!\n\n"
                 f"📍 Доступные регионы: {groups_text}\n"
                 f"💼 Должность: {position}\n"
                 f"🔐 Роль: Администратор\n\n"
                 f"🎉 Добро пожаловать в систему мониторинга!\n"
                 "Теперь вы можете использовать все функции бота. Нажмите /start для начала работы.",
            parse_mode='Markdown'
        )
        
        # Обновляем сообщение с результатом
        await query.edit_message_text(
            f"✅ ЗАЯВКА ПОДТВЕРЖДЕНА\n\n"
            f"👤 {fio}\n"
            f"🗺️ Регионы: {groups_text}\n"
            f"💼 Должность: {position}\n"
            f"⏰ Подтверждено: {query.message.date.strftime('%d.%m.%Y %H:%M')}",
            parse_mode='Markdown'
        )
        
        # Удаляем данные из временного хранилища
        remove_pending_registration(registration_id)
        
        # Открепляем сообщение
        try:
            await query.get_bot().unpin_chat_message(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id
            )
        except Exception as e:
            logger.debug(f"Не удалось открепить сообщение: {e}")
            
    except Exception as e:
        logger.error(f"Ошибка подтверждения регистрации: {e}")
        await query.answer("Ошибка при подтверждении регистрации", show_alert=True)


async def handle_reject_registration_new(query, callback_data: str):
    """Новый обработчик отклонения регистрации с коротким ID"""
    from src.bot.handlers.admin import get_pending_registration, remove_pending_registration
    
    registration_id = callback_data.split(":")[1]
    registration_data = get_pending_registration(registration_id)
    
    if not registration_data:
        await query.answer("❌ Данные регистрации не найдены", show_alert=True)
        return
        
    user_chat_id = registration_data['chat_id']
    fio = registration_data['fio']
    
    logger.info(f"Отклонение регистрации для {user_chat_id}")
    
    try:
        # УДАЛЯЕМ данные из admins.json если они там есть
        from src.core.storage import AdminManager
        AdminManager.remove_admin(user_chat_id)
        
        # Уведомляем пользователя
        await query.get_bot().send_message(
            chat_id=user_chat_id,
            text="❌ Ваша регистрация отклонена\n\n"
                 "Обратитесь к администратору для получения дополнительной информации.",
            parse_mode='Markdown'
        )
        
        # Обновляем сообщение с результатом
        await query.edit_message_text(
            f"❌ ЗАЯВКА ОТКЛОНЕНА\n\n"
            f"👤 {fio}\n"
            f"⏰ Отклонено: {query.message.date.strftime('%d.%m.%Y %H:%M')}",
            parse_mode='Markdown'
        )
        
        # Удаляем данные из временного хранилища
        remove_pending_registration(registration_id)
        
        # Открепляем сообщение
        try:
            await query.get_bot().unpin_chat_message(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id
            )
        except Exception as e:
            logger.debug(f"Не удалось открепить сообщение: {e}")
            
    except Exception as e:
        logger.error(f"Ошибка отклонения регистрации: {e}")
        await query.answer("Ошибка при отклонении регистрации", show_alert=True)


async def handle_help_sections(query, section: str):
    """Обработчик секций помощи (заглушки)"""
    from src.bot.keyboards import get_help_keyboard
    
    keyboard = get_help_keyboard()
    
    section_names = {
        "help_manual": "📖 Руководство пользователя",
        "help_support": "🔧 Техподдержка", 
        "help_contacts": "📞 Контакты",
        "help_faq": "❓ FAQ",
        "help_terms": "📋 Пользовательское соглашение",
        "help_license": "📄 Лицензия",
        "help_codereview": "🔍 CodeReview",
        "help_status": "📊 Статус системы",
        "help_changelog": "🔄 История изменений",
        "help_videos": "📺 Видеоинструкции"
    }
    
    section_name = section_names.get(section, "Помощь")
    
    message = f"""
{section_name}

🚧 Функционал не готов, ведётся разработка.

В ближайшее время здесь будет доступна подробная информация по данному разделу.

Пока что воспользуйтесь основными функциями бота через главное меню.
    """
    
    await safe_edit_with_keyboard(query, message, reply_markup=keyboard, parse_mode=None)


