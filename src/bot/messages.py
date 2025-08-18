"""
Модуль форматирования сообщений для Telegram бота
"""
from datetime import datetime
from typing import Dict, List, Any
from ..core.monitoring import format_timestamp
from ..core.storage import ThresholdManager
from ..utils.validators import sanitize_string, escape_markdown




def format_sensor_message(sensor: Dict[str, Any], escape_md: bool = False) -> str:
    """
    Форматирует данные датчика в читаемое сообщение
    
    Args:
        sensor: Данные датчика
        escape_md: Экранировать ли символы маркдауна
        
    Returns:
        Отформатированное сообщение
    """
    try:
        device_id = sanitize_string(str(sensor.get("device_id", "Неизвестно")))
        group = sanitize_string(str(sensor.get("group", "Неизвестно")))
        temperature = sensor.get("temperature", 0)
        validation_status = sensor.get("validation_status", "unknown")
        validation_errors = sensor.get("validation_errors", [])
        
        # Безопасная обработка timestamp
        try:
            timestamp = int(sensor.get("timestamp", int(datetime.now().timestamp())))
            formatted_time = format_timestamp(timestamp)
        except (ValueError, TypeError):
            formatted_time = "Некорректное время"
        
        # Безопасная обработка температуры
        try:
            temp_value = float(temperature) if temperature not in [None, "", "invalid"] else 0
        except (ValueError, TypeError):
            temp_value = 0
            temperature = "Некорректно"
        
        # Получаем пороговые значения для датчика
        raw_device_id = sensor.get("device_id", "")
        threshold_info = ""
        min_temp_value = None
        max_temp_value = None
        
        try:
            threshold = ThresholdManager.get_device_threshold(raw_device_id, group)
            if threshold:
                min_temp_value = threshold.get('min')
                max_temp_value = threshold.get('max')
                min_temp_display = min_temp_value if min_temp_value is not None else 'не задан'
                max_temp_display = max_temp_value if max_temp_value is not None else 'не задан'
                threshold_info = f"📊 Пороги: {min_temp_display}°C — {max_temp_display}°C"
            else:
                threshold_info = "📊 Пороги: не настроены"
        except Exception:
            threshold_info = "📊 Пороги: ошибка загрузки"
        
        # Определяем иконку и статус валидности
        if validation_status == "invalid":
            status_icon = "⚠️"
            temp_icon = "❓"
        else:
            status_icon = "✅"
            # Определяем иконку на основе температуры и пороговых значений для валидных данных
            if min_temp_value is not None and temp_value < min_temp_value:
                temp_icon = "🥶"
            elif max_temp_value is not None and temp_value > max_temp_value:
                temp_icon = "🥵"
            elif (min_temp_value is not None and max_temp_value is not None and 
                  min_temp_value <= temp_value <= max_temp_value):
                temp_icon = "👍"
            else:
                temp_icon = "🚨"

        message_parts = [
            f"{status_icon} {temp_icon} {escape_markdown(device_id) if escape_md else device_id}",
            f"📍 Группа: {group}",
            f"🌡️ Температура: {temperature}°C",
            threshold_info,
            f"⏰ Время: {formatted_time}"
        ]
        
        # Добавляем предупреждения для невалидных данных
        if validation_status == "invalid" and validation_errors:
            message_parts.append("")
            message_parts.append("⚠️ ПРЕДУПРЕЖДЕНИЕ - НЕВАЛИДНЫЕ ДАННЫЕ:")
            for error in validation_errors:
                message_parts.append(f"• {error}")
        
        return "\n".join(message_parts)
        
    except Exception as e:
        return f"❌ Ошибка форматирования данных датчика: {str(e)}"


def format_group_sensors_message(group_name: str, sensors: List[Dict[str, Any]]) -> str:
    """
    Форматирует список датчиков группы
    
    Args:
        group_name: Название группы
        sensors: Список датчиков
        
    Returns:
        Отформатированное сообщение
    """
    if not sensors:
        return f"📊 **Группа: {group_name}**\n\n❌ Нет доступных данных датчиков"
    
    # Подсчитываем статистику по валидности данных
    valid_sensors = [s for s in sensors if s.get('validation_status') == 'valid']
    invalid_sensors = [s for s in sensors if s.get('validation_status') == 'invalid']
    
    # Формируем заголовок с дополнительной информацией
    header = f"📊 Группа: {group_name} ({len(sensors)} датчиков)"
    if invalid_sensors:
        header += f"\n⚠️ Невалидных данных: {len(invalid_sensors)} из {len(sensors)}"
    
    message_parts = [header, "=" * 30]
    
    # Сначала показываем валидные датчики
    for sensor in valid_sensors:
        sensor_msg = format_sensor_message(sensor)
        message_parts.append(sensor_msg)
        message_parts.append("-" * 20)
    
    # Затем показываем невалидные датчики с пометкой
    if invalid_sensors:
        message_parts.append("⚠️ ДАТЧИКИ С НЕВАЛИДНЫМИ ДАННЫМИ:")
        message_parts.append("=" * 25)
        for sensor in invalid_sensors:
            sensor_msg = format_sensor_message(sensor)
            message_parts.append(sensor_msg)
            message_parts.append("-" * 20)
    
    return "\n".join(message_parts)


def format_welcome_message(fio: str = "", position: str = "", is_new_user: bool = True, chat_id: int = None) -> str:
    """
    Форматирует приветственное сообщение
    
    Args:
        fio: ФИО пользователя
        position: Должность пользователя
        is_new_user: Новый ли пользователь
        chat_id: ID чата пользователя
        
    Returns:
        Приветственное сообщение
    """
    if is_new_user:
        message = (
            "👋 **Добро пожаловать в CelsiusPulse Bot!**\n\n"
            "🌡️ Система мониторинга температуры складских помещений\n"
        )
        
        if chat_id:
            message += f"🆔 Ваш чат ID: `{chat_id}`\n\n"
        else:
            message += "\n"
            
        message += (
            "📝 Для продолжения работы необходима регистрация.\n"
            "Укажите полное ФИО в формате: Иванов Иван Иванович\n\n"
            "💡 Если нужно сбросить регистрацию, напишите: **сброс**"
        )
        
        return message
    else:
        greeting = f"👋 **Добро пожаловать, {fio}!**\n\n"
        if position:
            greeting += f"💼 Должность: {position}\n\n"
        
        greeting += (
            "🌡️ **CelsiusPulse Bot** - мониторинг температуры\n\n"
            "Выберите действие из меню ниже:"
        )
        return greeting


def format_alert_message(sensor: Dict[str, Any], alert_type: str, threshold_info: str = "") -> str:
    """
    Форматирует сообщение об превышении пороговых значений
    
    Args:
        sensor: Данные датчика
        alert_type: Тип тревоги ('high', 'low')  
        threshold_info: Информация о пороговых значениях
        
    Returns:
        Сообщение тревоги
    """
    device_id = sanitize_string(str(sensor.get("device_id", "Неизвестно")))
    group = sanitize_string(str(sensor.get("group", "Неизвестно")))
    temperature = sensor.get("temperature", 0)
    timestamp = sensor.get("timestamp", int(datetime.now().timestamp()))
    
    # Иконки для разных типов тревог
    alert_icons = {
        'high': '🔥🚨',
        'low': '🥶❄️',
        'critical': '⚠️🆘'
    }
    
    icon = alert_icons.get(alert_type, '⚠️')
    
    message = (
        f"{icon} ТЕМПЕРАТУРНАЯ ТРЕВОГА {icon}\n\n"
        f"🏷️ Датчик: {escape_markdown(device_id)}\n"
        f"📍 Группа: {group}\n"
        f"🌡️ Температура: {temperature}°C\n"
        f"⏰ Время: {format_timestamp(timestamp)}\n"
    )
    
    if threshold_info:
        message += f"📊 Пороги: {threshold_info}\n"
    
    message += "\n🔔 Требуется внимание!"
    
    return message


def format_admin_list_message(admins: List[Dict[str, Any]]) -> str:
    """
    Форматирует список администраторов
    
    Args:
        admins: Список администраторов
        
    Returns:
        Отформатированное сообщение
    """
    if not admins:
        return "👥 Список администраторов\n\n❌ Нет зарегистрированных администраторов"
    
    message_parts = [f"👥 Список администраторов ({len(admins)} чел.)"]
    message_parts.append("=" * 40)
    
    for i, admin in enumerate(admins, 1):
        fio = admin.get('fio', 'Не указано')
        position = admin.get('position', 'Не указана')
        groups = admin.get('groups', [])
        registered = admin.get('registered', 'Неизвестно')
        
        admin_info = (
            f"{i}. {fio}\n"
            f"💼 Должность: {position}\n"
            f"📋 Группы: {', '.join(groups) if groups else 'Нет назначенных групп'}\n"
            f"📅 Регистрация: {registered}"
        )
        
        message_parts.append(admin_info)
        message_parts.append("-" * 25)
    
    return "\n".join(message_parts)


def format_thresholds_message(thresholds: Dict[str, Any]) -> str:
    """
    Форматирует пороговые значения
    
    Args:
        thresholds: Словарь с пороговыми значениями
        
    Returns:
        Отформатированное сообщение
    """
    if not thresholds:
        return "📊 Пороговые значения\n\n❌ Нет настроенных пороговых значений"
    
    message_parts = ["📊 Пороговые значения температуры"]
    message_parts.append("=" * 40)
    
    for group_name, devices in thresholds.items():
        if isinstance(devices, dict):
            message_parts.append(f"📍 Группа: {group_name}")
            
            for device_id, values in devices.items():
                if isinstance(values, dict):
                    min_temp = values.get('min', 'не указан')
                    max_temp = values.get('max', 'не указан') 
                    
                    device_info = (
                        f"  🌡️ {escape_markdown(device_id)}: "
                        f"{min_temp}°C — {max_temp}°C"
                    )
                    message_parts.append(device_info)
            
            message_parts.append("")
    
    return "\n".join(message_parts)


def format_statistics_message(stats: Dict[str, Any]) -> str:
    """
    Форматирует статистику системы с расшифровкой проблем
    
    Args:
        stats: Словарь со статистикой
        
    Returns:
        Отформатированное сообщение
    """
    total = stats.get('total_sensors', 0)
    valid = stats.get('valid_sensors', 0)
    invalid = stats.get('invalid_sensors', 0)
    critical = stats.get('critical_sensors', 0)
    
    # Основная статистика (компактный формат)
    message = (
        "📈 Статистика системы\n\n"
        f"🌡️ Всего датчиков: {total}  \n"
        f"✅ Валидных: {valid} | ⚠️ Невалидных: {invalid} | 🔥 Критических: {critical}\n"
        f"📊 Групп: {stats.get('total_groups', 0)} | 🕐 Обновлено: {stats.get('last_update', 'Неизвестно')}"
    )
    
    # Расшифровка проблем (если есть)
    validation_errors = stats.get('validation_errors_analysis', {})
    critical_issues = stats.get('critical_issues_analysis', {})
    groups_breakdown = stats.get('groups_breakdown', {})
    problem_sensors = stats.get('problem_sensors', {})
    
    if validation_errors or critical_issues:
        message += "\n\n🔍 Проблемы:"
        
        # Расшифровка невалидных датчиков
        if validation_errors:
            error_parts = []
            for error_type, count in validation_errors.items():
                error_parts.append(f"{error_type} ({count})")
            message += f"\n⚠️ Невалидные: {', '.join(error_parts)}"
        
        # Расшифровка критических проблем
        if critical_issues:
            critical_parts = []
            for issue_type, count in critical_issues.items():
                critical_parts.append(f"{issue_type} ({count})")
            message += f"\n🔥 Критические: {', '.join(critical_parts)}"
    
    # Список конкретных проблемных датчиков или сообщение "все в порядке"
    if groups_breakdown:
        # Проверяем, есть ли проблемы в группах
        has_problems = False
        for group_stats in groups_breakdown.values():
            if group_stats.get('critical', 0) > 0 or group_stats.get('invalid', 0) > 0:
                has_problems = True
                break
        
        if not has_problems and invalid == 0 and critical == 0:
            # Если нет проблем вообще - показываем успокаивающее сообщение
            message += "\n\n🌙💤 Показатели в рамках допустимых значений. Спите спокойно 😴✨"
        else:
            # Если есть проблемы - показываем конкретные проблемные датчики
            message += "\n\n📊 Проблемные датчики:"
            
            # Показываем критические датчики
            critical_sensors = problem_sensors.get('critical', [])
            if critical_sensors:
                for sensor in critical_sensors[:5]:  # Ограничиваем до 5 для компактности
                    device_id = sensor.get('device_id', 'N/A')
                    group = sensor.get('group', 'N/A')
                    
                    # Импортируем функцию для получения эмодзи (локальный импорт)
                    from ..core.monitoring import get_sensor_problem_emoji_and_description
                    emoji, description = get_sensor_problem_emoji_and_description(sensor, is_critical=True)
                    message += f"\n{emoji} {group}/{device_id}: {description}"
            
            # Показываем невалидные датчики
            invalid_sensors = problem_sensors.get('invalid', [])
            if invalid_sensors:
                for sensor in invalid_sensors[:5]:  # Ограничиваем до 5 для компактности
                    device_id = sensor.get('device_id', 'N/A')
                    group = sensor.get('group', 'N/A')
                    
                    # Импортируем функцию для получения эмодзи (локальный импорт)
                    from ..core.monitoring import get_sensor_problem_emoji_and_description
                    emoji, description = get_sensor_problem_emoji_and_description(sensor, is_critical=False)
                    message += f"\n{emoji} {group}/{device_id}: {description}"
            
            # Показываем общее количество если датчиков больше лимита
            total_problems = len(critical_sensors) + len(invalid_sensors)
            if total_problems > 10:
                message += f"\n... и ещё {total_problems - 10} проблемных датчиков"
    
    return message


def format_error_message(error_type: str, details: str = "") -> str:
    """
    Форматирует сообщение об ошибке
    
    Args:
        error_type: Тип ошибки
        details: Детали ошибки
        
    Returns:
        Сообщение об ошибке
    """
    error_messages = {
        'access_denied': '🚫 **Доступ запрещен**\n\nУ вас недостаточно прав для выполнения этого действия.',
        'invalid_input': '❌ **Неверный ввод**\n\nПожалуйста, проверьте формат введенных данных.',
        'data_not_found': '🔍 **Данные не найдены**\n\nЗапрашиваемая информация отсутствует.',
        'system_error': '⚠️ **Системная ошибка**\n\nПроизошла техническая ошибка. Попробуйте позже.',
        'rate_limited': '⏳ **Превышен лимит запросов**\n\nСлишком много запросов. Подождите немного.',
        'maintenance': '🔧 **Техническое обслуживание**\n\nСистема временно недоступна.'
    }
    
    message = error_messages.get(error_type, '❌ **Неизвестная ошибка**')
    
    if details:
        message += f"\n\n📝 Детали: {sanitize_string(details)}"
    
    return message