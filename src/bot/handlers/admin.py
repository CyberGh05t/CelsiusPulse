"""
Обработчики административных функций и текстового ввода
"""
import re
from telegram import Update
from telegram.ext import ContextTypes
from src.config.logging import SecureLogger
from src.core.auth import get_user_role, add_user_to_group, update_env_file
from src.core.storage import AdminManager
from src.core.monitoring import get_all_groups
from src.core.registration_manager import registration_manager
from src.core.threshold_context_manager import threshold_context_manager
from src.services.bot_service import BotService
from src.bot.messages import format_welcome_message, format_error_message
from src.bot.keyboards import get_main_keyboard, get_quick_main_keyboard, get_persistent_keyboard
from src.bot.utils import reply_with_keyboard, send_message_with_persistent_keyboard
from src.utils.security import validate_request_security
from src.utils.validators import validate_user_input

logger = SecureLogger(__name__)

# ПРИМЕЧАНИЕ: Основная логика обработки ввода перенесена в новые модули:
# - src.bot.handlers.input_handlers - обработка текстового ввода
# - src.bot.handlers.registration_handlers - обработка регистрации
# - src.services.bot_service - бизнес-логика
# Этот файл содержит старые функции для совместимости и будет постепенно рефакторизован


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик текстовых сообщений - перенаправляет на новый InputHandler
    
    DEPRECATED: Эта функция оставлена для совместимости.
    Используйте src.bot.handlers.input_handlers.InputHandler.handle_text_input
    """
    from src.bot.handlers.input_handlers import InputHandler
    return await InputHandler.handle_text_input(update, context)


# УСТАРЕЛО: Алиас для совместимости - теперь используется новая система регистрации
async def handle_user_registration(update: Update, text: str, chat_id: int):
    """Переадресация на новую систему регистрации"""
    from src.bot.handlers.input_handlers import handle_registration_input
    await handle_registration_input(update, text, chat_id)

# Заглушка для обратной совместимости старых callback'ов
handle_user_registration.temp_storage = {}


async def handle_registration_reset(update: Update, chat_id: int):
    """
    Обрабатывает сброс регистрации пользователя
    """
    logger.info(f"Сброс регистрации для пользователя {chat_id}")
    
    # Очищаем данные регистрации
    if hasattr(handle_user_registration, 'temp_storage'):
        handle_user_registration.temp_storage.pop(chat_id, None)
    
    # Показываем сообщение о сбросе и начинаем заново
    from src.bot.messages import format_welcome_message
    
    # При сбросе регистрации НЕ добавляем кнопку главного меню - пользователь остается в процессе регистрации
    await update.message.reply_text(
        "🔄 **Регистрация сброшена**\n\n"
        "Все данные очищены. Начинаем регистрацию заново:",
        parse_mode='Markdown'
    )
    
    # Показываем приветственное сообщение БЕЗ кнопки главного меню
    welcome_message = format_welcome_message(is_new_user=True, chat_id=chat_id)
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def show_region_selection(update: Update, chat_id: int):
    """
    Показывает список регионов для выбора с поддержкой множественного выбора
    """
    from src.core.monitoring import get_all_groups
    from src.bot.keyboards import get_registration_groups_keyboard
    
    # Получаем контекст для определения уже выбранных групп
    if not hasattr(handle_user_registration, 'temp_storage'):
        handle_user_registration.temp_storage = {}
    context = handle_user_registration.temp_storage.get(chat_id, {})
    selected_groups = context.get('selected_groups', [])
    
    available_groups = get_all_groups()
    keyboard = get_registration_groups_keyboard(available_groups, selected_groups)
    
    message_text = "🗺️ **Выберите регион(ы):**\n\n"
    if selected_groups:
        message_text += f"✅ Уже выбрано: {', '.join(selected_groups)}\n\n"
    message_text += "💡 Можете выбрать несколько регионов"
    
    # В процессе регистрации НЕ добавляем кнопку главного меню!
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )



async def send_registration_request_to_big_boss(update: Update, chat_id: int, fio: str, selected_groups: list, position: str):
    """
    Отправляет запрос на подтверждение регистрации назначенному big_boss
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import os
    import uuid
    
    # Получаем ID уполномоченного на регистрацию Big Boss из .env
    approver_id = os.getenv('REGISTRATION_APPROVER_ID')
    if not approver_id:
        logger.error("REGISTRATION_APPROVER_ID не задан в .env файле")
        raise ValueError("Не настроен уполномоченный для регистрации пользователь")
    
    try:
        approver_chat_id = int(approver_id)
    except ValueError:
        logger.error(f"Неверный формат REGISTRATION_APPROVER_ID: {approver_id}")
        raise ValueError("REGISTRATION_APPROVER_ID должен быть числом")
    
    groups_text = ', '.join(selected_groups) if selected_groups else 'Не выбраны'
    
    # Создаем короткий уникальный ID для callback_data
    registration_id = str(uuid.uuid4())[:8]
    
    # Сохраняем данные во временное хранилище
    if not hasattr(send_registration_request_to_big_boss, '_pending_registrations'):
        send_registration_request_to_big_boss._pending_registrations = {}
    
    send_registration_request_to_big_boss._pending_registrations[registration_id] = {
        'chat_id': chat_id,
        'fio': fio,
        'groups': selected_groups,
        'position': position
    }
    
    request_message = (
        "🆕 **НОВАЯ ЗАЯВКА НА РЕГИСТРАЦИЮ**\n\n"
        f"👤 Пользователь: {fio}\n"
        f"🆔 Chat ID: `{chat_id}`\n"
        f"🗺️ Регион(ы): {groups_text}\n"
        f"💼 Должность: {position}\n"
        f"📅 Дата: {update.message.date.strftime('%d.%m.%Y %H:%M')}"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_reg:{registration_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_reg:{registration_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        bot = update.get_bot()
        sent_message = await bot.send_message(
            chat_id=approver_chat_id,
            text=request_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Закрепляем сообщение для важности
        await bot.pin_chat_message(
            chat_id=approver_chat_id,
            message_id=sent_message.message_id
        )
        
        logger.info(f"Запрос на регистрацию {chat_id} отправлен уполномоченному big_boss {approver_chat_id}")
        
    except Exception as e:
        logger.error(f"Ошибка отправки запроса уполномоченному big_boss: {e}")


def get_pending_registration(registration_id: str):
    """Получает данные ожидающей регистрации по ID"""
    if hasattr(send_registration_request_to_big_boss, '_pending_registrations'):
        return send_registration_request_to_big_boss._pending_registrations.get(registration_id)
    return None


def remove_pending_registration(registration_id: str):
    """Удаляет данные ожидающей регистрации по ID"""
    if hasattr(send_registration_request_to_big_boss, '_pending_registrations'):
        send_registration_request_to_big_boss._pending_registrations.pop(registration_id, None)




def validate_position(position: str) -> bool:
    """
    Валидация должности с защитой от бессмысленных данных
    """
    if not position or not isinstance(position, str):
        return False
    
    position = position.strip()
    
    # Проверка длины
    if len(position) < 2 or len(position) > 50:
        return False
    
    # Проверка на подозрительные паттерны
    position_lower = position.lower()
    
    # Запрещенные паттерны для должности
    suspicious_patterns = [
        r'^test', r'^тест', r'^spam', r'^спам', r'^fake', r'^фейк',
        r'qwerty', r'asdf', r'123456', r'admin', r'user',
        r'aaa+', r'ааа+', r'xxx', r'ыыы+',
        r'([a-zа-я])\1{3,}',  # 4+ одинаковых символа подряд
        r'^[a-zа-я]{1,2}$',  # Слишком короткие (1-2 символа)
        r'^\d+$',  # Только цифры
        r'^[\-\.\(\)\s]+$'  # Только знаки препинания
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, position_lower):
            return False
    
    # Разрешенные символы: буквы, цифры, пробелы, дефисы, точки, скобки
    if not re.match(r'^[А-Яа-яЁёA-Za-z0-9\s\-\.\(\)]+$', position):
        return False
    
    # Должна содержать минимум одну букву
    if not re.search(r'[А-Яа-яЁёA-Za-z]', position):
        return False
    
    # Не должна состоять только из пробелов и знаков препинания
    if re.match(r'^[\s\-\.\(\)0-9]+$', position):
        return False
    
    # Проверка на разумное количество слов (1-4 слова)
    words = position.split()
    if len(words) == 0 or len(words) > 4:
        return False
    
    # Каждое слово должно быть осмысленным
    for word in words:
        if len(word) < 2 and word not in ['и', 'в', 'по', 'на', 'от', 'к']:
            return False
    
    return True


def validate_registration_context(context: dict, required_step: str) -> bool:
    """
    Валидация контекста регистрации
    """
    if not context or not isinstance(context, dict):
        return False
    
    current_step = context.get('registration_step')
    if current_step != required_step:
        return False
    
    # Проверяем, что все предыдущие шаги выполнены
    if required_step == 'region' and not context.get('fio'):
        return False
    elif required_step == 'position' and (not context.get('fio') or not context.get('selected_groups')):
        return False
    
    return True


def parse_registration_data(text: str) -> tuple[str, str] | None:
    """
    Парсит данные регистрации из текста
    
    Args:
        text: Текст с данными регистрации
        
    Returns:
        Кортеж (ФИО, должность) или None при ошибке
    """
    # Удаляем лишние пробелы
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Пробуем разделить по запятой
    if ',' in text:
        parts = text.split(',', 1)
        if len(parts) == 2:
            fio = parts[0].strip()
            position = parts[1].strip()
            
            # Валидация ФИО (минимум 2 слова)
            if len(fio.split()) < 2:
                return None
            
            # Валидация должности (не пустая)
            if not position:
                return None
            
            return fio, position
    
    # Пробуем разделить по последнему пробелу (если много слов)
    words = text.split()
    if len(words) >= 3:
        # Предполагаем, что последнее слово - должность
        fio = ' '.join(words[:-1])
        position = words[-1]
        return fio, position
    
    return None


async def handle_threshold_input(update: Update, text: str, chat_id: int) -> bool:
    """
    Обработка ввода пороговых значений с редактированием исходного сообщения
    
    Returns:
        True если ввод был обработан как пороговые значения
    """
    from src.bot.handlers.callbacks import handle_set_threshold_device
    from src.core.storage import ThresholdManager
    from src.core.auth import can_access_group
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    # Проверяем, есть ли контекст для пороговых значений через новую систему
    user_id = update.effective_user.id
    context = threshold_context_manager.get_context(user_id)
    
    logger.info(f"Проверка контекста для пороговых значений от пользователя {user_id}: context={context}")
    
    if not context:
        return False
    
    action = context.action
    group_name = context.group_name
    device_id = context.device_id
    stored_message_id = context.message_id
    stored_chat_id = context.chat_id
    
    if not action or not group_name or not stored_message_id:
        return False
    
    # Получаем bot instance для редактирования сообщения
    bot = update.get_bot()
    
    # Проверяем доступ к группе (пропускаем для массовых операций)
    if group_name not in ['USER', 'ALL'] and not can_access_group(chat_id, group_name):
        try:
            # Редактируем исходное сообщение с ошибкой доступа
            keyboard = [[InlineKeyboardButton("🔙 Назад к группам", callback_data="settings_thresholds")]]
            await bot.edit_message_text(
                chat_id=stored_chat_id,
                message_id=stored_message_id,
                text="❌ Нет доступа к этой группе\n\nВернитесь к выбору групп для продолжения",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения об ошибке доступа: {e}")
        # Очищаем контекст через новую систему
        threshold_context_manager.clear_context(user_id)
        return True
    
    # Парсим пороговые значения в формате "мин макс"
    try:
        # Очищаем текст от markdown символов и лишних пробелов
        clean_text = text.strip().replace('`', '').replace('*', '')
        parts = clean_text.split()
        
        logger.info(f"Парсинг пороговых значений от {chat_id}: исходный='{text}', очищенный='{clean_text}', части={parts}")
        
        # Удаляем сообщение пользователя с вводом
        try:
            await update.message.delete()
            logger.info(f"Удалено сообщение пользователя с вводом порогов от {chat_id}")
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")
        
        # Функция для редактирования исходного сообщения с ошибкой
        async def edit_with_error(error_text: str):
            try:
                back_callback = "settings_thresholds" if group_name in ['USER', 'ALL'] else f"change_threshold_{group_name}"
                keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
                await bot.edit_message_text(
                    chat_id=stored_chat_id,
                    message_id=stored_message_id,
                    text=f"{error_text}\n\nПопробуйте ещё раз или вернитесь назад",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения с ошибкой: {e}")
        
        if len(parts) != 2:
            await edit_with_error(
                f"❌ **Неверный формат**\n\n"
                f"Получено {len(parts)} значений вместо 2\n"
                f"Используйте: `мин макс`\n"
                f"Например: `18 25`"
            )
            return True
        
        try:
            min_temp = float(parts[0])
            max_temp = float(parts[1])
        except ValueError as ve:
            await edit_with_error(
                f"❌ **Ошибка парсинга чисел**\n\n"
                f"Получены значения: `{parts[0]}` и `{parts[1]}`\n"
                f"Используйте только числа, например: `18 25`"
            )
            return True
        
        if min_temp >= max_temp:
            await edit_with_error("❌ **Неверные значения**\n\nМинимальная температура должна быть меньше максимальной")
            return True
        
        if min_temp < -50 or max_temp > 100:
            await edit_with_error("❌ **Недопустимый диапазон**\n\nТемпературы должны быть от -50°C до 100°C")
            return True
        
        if abs(max_temp - min_temp) < 1.0:
            await edit_with_error("❌ **Слишком малая разность**\n\nРазность между мин и макс должна быть не менее 1°C")
            return True
        
        # Сохраняем пороговые значения
        success = False
        
        if action == 'set_threshold_group' and device_id == 'ALL':
            # Устанавливаем пороги для всей группы
            from src.core.monitoring import get_sensors_by_group
            sensors = get_sensors_by_group(group_name)
            success_count = 0
            
            for sensor in sensors:
                sensor_device_id = sensor['device_id']
                try:
                    if ThresholdManager.set_device_threshold(sensor_device_id, group_name, min_temp, max_temp):
                        success_count += 1
                except Exception as e:
                    logger.error(f"Ошибка установки порога для {sensor_device_id}: {e}")
            
            success = success_count > 0
            
            if success:
                # Редактируем исходное сообщение с результатом
                try:
                    keyboard = [[InlineKeyboardButton("🔙 Назад к устройствам", callback_data=f"change_threshold_{group_name}")]]
                    await bot.edit_message_text(
                        chat_id=stored_chat_id,
                        message_id=stored_message_id,
                        text=f"✅ **Пороговые значения установлены для группы {group_name}**\n\n"
                             f"🌡️ Минимум: {min_temp}°C\n"
                             f"🌡️ Максимум: {max_temp}°C\n"
                             f"📊 Обновлено устройств: {success_count}/{len(sensors)}",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка при редактировании сообщения с успехом: {e}")
            else:
                try:
                    keyboard = [[InlineKeyboardButton("🔙 Назад к устройствам", callback_data=f"change_threshold_{group_name}")]]
                    await bot.edit_message_text(
                        chat_id=stored_chat_id,
                        message_id=stored_message_id,
                        text="❌ **Ошибка при сохранении**\n\nПороговые значения не удалось установить",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка при редактировании сообщения с ошибкой: {e}")
            
        elif action == 'set_threshold_device':
            # Устанавливаем пороги для конкретного устройства
            try:
                success = ThresholdManager.set_device_threshold(device_id, group_name, min_temp, max_temp)
            except Exception as e:
                logger.error(f"Ошибка установки порога для {device_id}: {e}")
                success = False
            
            if success:
                # Редактируем исходное сообщение с результатом
                try:
                    keyboard = [[InlineKeyboardButton("🔙 Назад к устройствам", callback_data=f"change_threshold_{group_name}")]]
                    safe_device_id = device_id.replace('_', '\\_')
                    await bot.edit_message_text(
                        chat_id=stored_chat_id,
                        message_id=stored_message_id,
                        text=f"✅ **Пороговые значения установлены для {safe_device_id}**\n\n"
                             f"🏢 Группа: {group_name}\n"
                             f"🌡️ Минимум: {min_temp}°C\n"
                             f"🌡️ Максимум: {max_temp}°C",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка при редактировании сообщения с успехом: {e}")
            else:
                try:
                    keyboard = [[InlineKeyboardButton("🔙 Назад к устройствам", callback_data=f"change_threshold_{group_name}")]]
                    await bot.edit_message_text(
                        chat_id=stored_chat_id,
                        message_id=stored_message_id,
                        text="❌ **Ошибка при сохранении**\n\nПороговые значения не удалось установить",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка при редактировании сообщения с ошибкой: {e}")
        
        elif action == 'set_threshold_all_sensors':
            # Устанавливаем пороги для ВСЕХ датчиков всех групп (только для big_boss)
            from src.core.monitoring import get_all_groups, get_sensors_by_group
            all_groups = get_all_groups()
            total_updated = 0
            total_sensors = 0
            
            for group in all_groups:
                sensors = get_sensors_by_group(group)
                total_sensors += len(sensors)
                
                for sensor in sensors:
                    sensor_device_id = sensor['device_id']
                    try:
                        if ThresholdManager.set_device_threshold(sensor_device_id, group, min_temp, max_temp):
                            total_updated += 1
                    except Exception as e:
                        logger.error(f"Ошибка установки порога для {sensor_device_id} в группе {group}: {e}")
            
            if total_updated > 0:
                try:
                    keyboard = [[InlineKeyboardButton("🔙 Назад к группам", callback_data="settings_thresholds")]]
                    await bot.edit_message_text(
                        chat_id=stored_chat_id,
                        message_id=stored_message_id,
                        text=f"🌍 **Пороговые значения установлены для ВСЕХ датчиков!**\n\n"
                             f"🌡️ Минимум: {min_temp}°C\n"
                             f"🌡️ Максимум: {max_temp}°C\n"
                             f"📊 Обновлено датчиков: {total_updated}/{total_sensors}\n"
                             f"📍 Затронуто групп: {len(all_groups)}",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка при редактировании сообщения с успехом: {e}")
            else:
                try:
                    keyboard = [[InlineKeyboardButton("🔙 Назад к группам", callback_data="settings_thresholds")]]
                    await bot.edit_message_text(
                        chat_id=stored_chat_id,
                        message_id=stored_message_id,
                        text="❌ **Ошибка при сохранении**\n\nПороговые значения не удалось установить",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка при редактировании сообщения с ошибкой: {e}")
        
        elif action == 'set_threshold_user_sensors':
            # Устанавливаем пороги для всех датчиков доступных пользователю групп
            from src.core.monitoring import get_sensors_by_group
            user_groups = context.get('user_groups', [])
            total_updated = 0
            total_sensors = 0
            
            for group in user_groups:
                sensors = get_sensors_by_group(group)
                total_sensors += len(sensors)
                
                for sensor in sensors:
                    sensor_device_id = sensor['device_id']
                    try:
                        if ThresholdManager.set_device_threshold(sensor_device_id, group, min_temp, max_temp):
                            total_updated += 1
                    except Exception as e:
                        logger.error(f"Ошибка установки порога для {sensor_device_id} в группе {group}: {e}")
            
            if total_updated > 0:
                try:
                    keyboard = [[InlineKeyboardButton("🔙 Назад к группам", callback_data="settings_thresholds")]]
                    await bot.edit_message_text(
                        chat_id=stored_chat_id,
                        message_id=stored_message_id,
                        text=f"🔧 **Пороговые значения установлены для всех ваших датчиков!**\n\n"
                             f"🌡️ Минимум: {min_temp}°C\n"
                             f"🌡️ Максимум: {max_temp}°C\n"
                             f"📊 Обновлено датчиков: {total_updated}/{total_sensors}\n"
                             f"📍 Затронуто групп: {', '.join(user_groups)} ({len(user_groups)})",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка при редактировании сообщения с успехом: {e}")
            else:
                try:
                    keyboard = [[InlineKeyboardButton("🔙 Назад к группам", callback_data="settings_thresholds")]]
                    await bot.edit_message_text(
                        chat_id=stored_chat_id,
                        message_id=stored_message_id,
                        text="❌ **Ошибка при сохранении**\n\nПороговые значения не удалось установить",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка при редактировании сообщения с ошибкой: {e}")
        
        # Очищаем контекст через новую систему
        threshold_context_manager.clear_context(user_id)
        
        logger.info(f"Пороговые значения обновлены пользователем {chat_id}: {group_name}/{device_id} = {min_temp}-{max_temp}")
        return True
        
    except ValueError:
        try:
            back_callback = "settings_thresholds" if group_name in ['USER', 'ALL'] else f"change_threshold_{group_name}"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
            await bot.edit_message_text(
                chat_id=stored_chat_id,
                message_id=stored_message_id,
                text="❌ **Неверные числовые значения**\n\nИспользуйте: `мин макс`\nНапример: `18.5 25.0`",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения с ошибкой ValueError: {e}")
        threshold_context_manager.clear_context(user_id)
        return True
    except Exception as e:
        logger.error(f"Ошибка обработки пороговых значений от {chat_id}: {e}")
        try:
            back_callback = "settings_thresholds" if group_name in ['USER', 'ALL'] else f"change_threshold_{group_name}"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
            await bot.edit_message_text(
                chat_id=stored_chat_id,
                message_id=stored_message_id,
                text="❌ **Системная ошибка**\n\nПроизошла ошибка при обработке пороговых значений",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e2:
            logger.error(f"Ошибка при редактировании сообщения с системной ошибкой: {e2}")
        # Очищаем контекст при ошибке
        threshold_context_manager.clear_context(user_id)
        return True


async def handle_unknown_command_in_existing_menu(update: Update, chat_id: int, text: str) -> bool:
    """
    Пытается найти последнее активное меню и отобразить ошибку в нём
    
    Returns:
        True если удалось отредактировать существующее меню
    """
    from src.bot.handlers.callbacks import handle_set_threshold_device
    from src.bot.utils import get_last_user_menu
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    # Удаляем сообщение пользователя с неизвестной командой
    try:
        await update.message.delete()
        logger.info(f"Удалено сообщение пользователя с неизвестной командой: '{text[:50]}'")
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение пользователя: {e}")
    
    bot = update.get_bot()
    
    # Приоритет 1: Проверяем контекст пороговых значений через новую систему
    user_id = update.effective_user.id
    threshold_context = threshold_context_manager.get_context(user_id)
    
    if threshold_context and threshold_context.message_id and threshold_context.chat_id:
        # Нашли активное меню пороговых значений
        try:
            stored_message_id = threshold_context.message_id
            stored_chat_id = threshold_context.chat_id
            group_name = threshold_context.group_name
            
            # Определяем кнопку возврата
            if group_name in ['USER', 'ALL']:
                back_callback = "settings_thresholds"
                back_text = "🔙 Назад к группам"
            else:
                back_callback = f"change_threshold_{group_name}"
                back_text = "🔙 Назад к устройствам"
            
            keyboard = [[InlineKeyboardButton(back_text, callback_data=back_callback)]]
            
            await bot.edit_message_text(
                chat_id=stored_chat_id,
                message_id=stored_message_id,
                text=f"❌ **Некорректный ввод**\n\n"
                     f"Получен: `{text[:50]}`\n\n"
                     f"Для установки порогов сначала выберите датчик или группу, "
                     f"а затем введите значения в формате: `мин макс`",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            logger.info(f"Отображена ошибка неизвестной команды в активном меню порогов для {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при редактировании активного меню порогов: {e}")
    
    # Приоритет 2: Проверяем последнее меню пользователя
    last_menu = get_last_user_menu(chat_id)
    
    if last_menu and last_menu.get('message_id') and last_menu.get('chat_id'):
        try:
            stored_message_id = last_menu.get('message_id')
            stored_chat_id = last_menu.get('chat_id')
            
            # Создаём клавиатуру главного меню
            from src.bot.keyboards import get_main_keyboard
            from src.core.auth import get_user_role
            
            role = get_user_role(chat_id)
            keyboard = get_main_keyboard(role)
            
            await bot.edit_message_text(
                chat_id=stored_chat_id,
                message_id=stored_message_id,
                text=f"❌ **Неизвестная команда**\n\n"
                     f"Получен: `{text[:30]}`\n\n"
                     f"Используйте меню для навигации по системе.",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            logger.info(f"Отображена ошибка неизвестной команды в последнем меню для {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при редактировании последнего меню: {e}")
    
    # Не нашли никаких активных меню
    return False


async def handle_url_input(update: Update, chat_id: int, text: str):
    """
    Обработчик сообщений со ссылками
    """
    # Проверка безопасности
    is_safe, error_msg = validate_request_security(chat_id, f"url:{text[:100]}")
    if not is_safe:
        await update.message.reply_text(format_error_message('rate_limited', error_msg))
        return
    
    logger.info(f"Получена ссылка от {chat_id}: {text[:100]}")
    
    # Удаляем сообщение со ссылкой
    try:
        await update.message.delete()
        logger.info(f"Удалено сообщение со ссылкой от {chat_id}")
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение со ссылкой: {e}")
    
    # Пытаемся отобразить ошибку в существующем меню
    url_handled = await handle_media_in_existing_menu(update, chat_id, "🔗 ссылка")
    if not url_handled:
        # Если не нашли активное меню, создаем главное меню с ошибкой
        logger.warning(f"Ссылка удалена, но активное меню не найдено для пользователя {chat_id}. Создаем главное меню.")
        
        from src.core.auth import get_user_role
        from src.bot.keyboards import get_main_keyboard
        
        role = get_user_role(chat_id)
        keyboard = get_main_keyboard(role)
        
        # Создаем главное меню с сообщением об ошибке
        sent_message = await update.get_bot().send_message(
            chat_id=chat_id,
            text=f"❌ **Неподдерживаемый тип сообщения**\n\n"
                 f"Получена: 🔗 ссылка\n\n"
                 f"Бот не работает со ссылками. Используйте кнопки меню для навигации.",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # ВАЖНО: Регистрируем созданное главное меню для отслеживания
        if sent_message:
            from src.bot.utils import track_user_menu
            track_user_menu(
                user_id=chat_id, 
                chat_id=chat_id, 
                message_id=sent_message.message_id, 
                menu_type="main",
                menu_context={}
            )


async def handle_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик всех типов медиа (картинки, видео, аудио, документы)
    Удаляет медиа-файлы и показывает ошибку в последнем активном меню
    """
    chat_id = update.effective_chat.id
    message = update.message
    
    # Определяем тип медиа
    media_type = "unknown"
    if message.photo:
        media_type = "🖼️ изображение"
    elif message.video:
        media_type = "🎥 видео"
    elif message.audio:
        media_type = "🎵 аудио"
    elif message.voice:
        media_type = "🎤 голосовое сообщение"
    elif message.video_note:
        media_type = "📹 видеосообщение"
    elif message.document:
        media_type = "📄 документ"
    elif message.sticker:
        media_type = "📎 стикер"
    elif message.animation:
        media_type = "📹 GIF-анимация"
    elif message.contact:
        media_type = "📞 контакт"
    elif message.location:
        media_type = "🗺️ геолокация"
    elif message.venue:
        media_type = "🏢 место"
    elif message.poll:
        media_type = "📊 опрос"
    elif message.dice:
        media_type = "🎲 кубик"
    elif message.game:
        media_type = "🎮 игра"
    elif message.invoice:
        media_type = "💳 счет/инвойс"
    elif message.successful_payment:
        media_type = "💰 платеж"
    elif message.passport_data:
        media_type = "🛂 паспортные данные"
    elif getattr(message, 'story', None):
        media_type = "📖 история"
    elif message.has_media_spoiler:
        media_type = "🙈 медиа со спойлером"
    elif message.has_protected_content:
        media_type = "🔒 защищенный контент"
    elif message.is_automatic_forward:
        media_type = "↪️ автопересылка"
    elif message.is_topic_message:
        media_type = "💬 сообщение топика"
    elif getattr(message, 'user_attachment', None):
        media_type = "📎 вложение пользователя"
    
    # Проверка безопасности
    is_safe, error_msg = validate_request_security(chat_id, f"media:{media_type}")
    if not is_safe:
        await message.reply_text(format_error_message('rate_limited', error_msg))
        return
    
    logger.info(f"Получено {media_type} от {chat_id}")
    
    # Удаляем медиа-сообщение
    try:
        await message.delete()
        logger.info(f"Удалено {media_type} от {chat_id}")
    except Exception as e:
        logger.warning(f"Не удалось удалить {media_type}: {e}")
    
    # Используем универсальную систему умного обновления
    from src.bot.utils import smart_update_current_menu
    
    media_handled = await smart_update_current_menu(
        update, 
        chat_id, 
        "Неподдерживаемый тип сообщения", 
        media_type
    )
    
    if not media_handled:
        # Если не нашли активное меню, создаем главное меню с ошибкой
        logger.warning(f"Медиа {media_type} удалено, но активное меню не найдено для пользователя {chat_id}. Создаем главное меню.")
        
        from src.core.auth import get_user_role
        from src.bot.keyboards import get_main_keyboard
        
        role = get_user_role(chat_id)
        keyboard = get_main_keyboard(role)
        
        # Создаем главное меню с сообщением об ошибке
        sent_message = await update.get_bot().send_message(
            chat_id=chat_id,
            text=f"❌ **Неподдерживаемый тип сообщения**\n\n"
                 f"Получен: {media_type}\n\n"
                 f"Бот работает только с текстовыми командами и кнопками меню.",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # ВАЖНО: Регистрируем созданное главное меню для отслеживания
        if sent_message:
            from src.bot.utils import track_user_menu
            track_user_menu(
                user_id=chat_id, 
                chat_id=chat_id, 
                message_id=sent_message.message_id, 
                menu_type="main",
                menu_context={}
            )


async def handle_media_in_existing_menu(update: Update, chat_id: int, media_type: str) -> bool:
    """
    Пытается найти последнее активное меню и отобразить ошибку о медиа
    
    Returns:
        True если удалось отредактировать существующее меню
    """
    from src.bot.handlers.callbacks import handle_set_threshold_device
    from src.bot.utils import get_last_user_menu
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    bot = update.get_bot()
    
    # Приоритет 1: Проверяем контекст пороговых значений через новую систему
    user_id = update.effective_user.id
    threshold_context = threshold_context_manager.get_context(user_id)
    
    if threshold_context and threshold_context.message_id and threshold_context.chat_id:
        try:
            stored_message_id = threshold_context.message_id
            stored_chat_id = threshold_context.chat_id
            group_name = threshold_context.group_name
            
            # Определяем кнопку возврата
            if group_name in ['USER', 'ALL']:
                back_callback = "settings_thresholds"
                back_text = "🔙 Назад к группам"
            else:
                back_callback = f"change_threshold_{group_name}"
                back_text = "🔙 Назад к устройствам"
            
            keyboard = [[InlineKeyboardButton(back_text, callback_data=back_callback)]]
            
            await bot.edit_message_text(
                chat_id=stored_chat_id,
                message_id=stored_message_id,
                text=f"❌ **Неподдерживаемый формат**\n\n"
                     f"Получен: {media_type}\n\n"
                     f"Для установки порогов используйте только текстовые сообщения в формате: `мин макс`",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            logger.info(f"Отображена ошибка {media_type} в активном меню порогов для {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при редактировании активного меню порогов для {media_type}: {e}")
    
    # Приоритет 2: Проверяем последнее меню пользователя
    last_menu = get_last_user_menu(chat_id)
    
    if last_menu and last_menu.get('message_id') and last_menu.get('chat_id'):
        try:
            stored_message_id = last_menu.get('message_id')
            stored_chat_id = last_menu.get('chat_id')
            
            # Создаём клавиатуру главного меню
            from src.bot.keyboards import get_main_keyboard
            from src.core.auth import get_user_role
            
            role = get_user_role(chat_id)
            keyboard = get_main_keyboard(role)
            
            await bot.edit_message_text(
                chat_id=stored_chat_id,
                message_id=stored_message_id,
                text=f"❌ **Неподдерживаемый тип сообщения**\n\n"
                     f"Получен: {media_type}\n\n"
                     f"Бот работает только с текстовыми командами и кнопками меню.",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            logger.info(f"Отображена ошибка {media_type} в последнем меню для {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при редактировании последнего меню для {media_type}: {e}")
    
    # Не нашли никаких активных меню
    return False




async def handle_invalid_content(update: Update, chat_id: int, _text: str, content_type: str):
    """
    Обрабатывает невалидный контент с универсальным умным обновлением меню
    
    Args:
        update: Объект обновления Telegram
        chat_id: ID чата
        _text: Исходный текст сообщения (не используется, но нужен для совместимости)
        content_type: Тип обнаруженного невалидного контента
    """
    # Удаляем сообщение пользователя
    try:
        await update.message.delete()
        logger.info(f"Удалено сообщение с невалидным контентом ({content_type}) от {chat_id}")
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение с невалидным контентом: {e}")
    
    # Используем новую универсальную систему умного обновления
    from src.bot.utils import smart_update_current_menu
    
    content_handled = await smart_update_current_menu(
        update, 
        chat_id, 
        "Неподдерживаемый тип сообщения", 
        content_type
    )
    
    if not content_handled:
        # Если не нашли активное меню, создаем главное меню с ошибкой
        logger.warning(f"Текстовый контент удален, но активное меню не найдено для пользователя {chat_id}. Создаем главное меню.")
        
        from src.core.auth import get_user_role
        from src.bot.keyboards import get_main_keyboard
        
        role = get_user_role(chat_id)
        keyboard = get_main_keyboard(role)
        
        # Создаем главное меню с сообщением об ошибке
        sent_message = await update.get_bot().send_message(
            chat_id=chat_id,
            text=f"❌ **Неподдерживаемый тип сообщения**\n\n"
                 f"Обнаружен: {content_type}\n\n"
                 f"Используйте кнопки главного меню для навигации.",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # ВАЖНО: Регистрируем созданное главное меню для отслеживания
        if sent_message:
            from src.bot.utils import track_user_menu
            track_user_menu(
                user_id=chat_id, 
                chat_id=chat_id, 
                message_id=sent_message.message_id, 
                menu_type="main",
                menu_context={}
            )


async def handle_registration_reset_with_smart_deletion(update: Update, chat_id: int, text: str):
    """
    Обработка команд сброса регистрации с умным удалением
    """
    # Удаляем сообщение пользователя
    try:
        await update.message.delete()
        logger.info(f"Удалено сообщение команды сброса от {chat_id}")
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение команды сброса: {e}")
    
    # Выполняем сброс регистрации
    await handle_registration_reset(update, chat_id)


async def handle_user_registration_with_smart_deletion(update: Update, text: str, chat_id: int) -> bool:
    """
    Обработка регистрации пользователя с умным удалением
    
    Returns:
        True если текст обработан как часть процесса регистрации
        False если текст не подходит для регистрации (нужно удалить)
    """
    # Проверяем, находится ли пользователь в процессе регистрации
    if not hasattr(handle_user_registration, 'temp_storage'):
        handle_user_registration.temp_storage = {}
    
    context = handle_user_registration.temp_storage.get(chat_id, {})
    registration_step = context.get('registration_step', 'fio')
    
    # Проверяем валидность шага регистрации
    valid_steps = ['fio', 'position']
    if registration_step not in valid_steps:
        # Неизвестный шаг регистрации - удаляем текст
        return False
    
    # Удаляем сообщение пользователя перед обработкой
    try:
        await update.message.delete()
        logger.info(f"Удалено сообщение регистрации (шаг: {registration_step}) от {chat_id}")
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение регистрации: {e}")
    
    # Обрабатываем шаги регистрации в существующих меню
    if registration_step == 'fio':
        # Шаг 1: Ввод ФИО
        if not validate_fio(text):
            # Неверный формат ФИО - показываем ошибку в существующем меню
            registration_handled = await handle_media_in_existing_menu(update, chat_id, "❌ неверный формат ФИО")
            if not registration_handled:
                # Если не нашли активное меню, создаем сообщение с инструкциями по регистрации
                logger.warning(f"Неверный ФИО, но активное меню не найдено для пользователя {chat_id}. Создаем сообщение регистрации.")
                
                sent_message = await update.get_bot().send_message(
                    chat_id=chat_id,
                    text="❌ **Неверный формат ФИО**\n\n"
                         "Пожалуйста, введите полное ФИО в формате:\n"
                         "`Иванов Иван Иванович`\n\n"
                         "Для отмены регистрации напишите: `сброс`",
                    parse_mode='Markdown'
                )
                
                # НЕ регистрируем это как меню, поскольку это временное сообщение
            return True
        
        # Сохраняем ФИО и переходим к выбору региона
        context['fio'] = text.strip()
        context['registration_step'] = 'region'
        context['selected_groups'] = []
        handle_user_registration.temp_storage[chat_id] = context
        
        # Показываем список регионов в существующем меню
        await show_region_selection_with_smart_menu(update, chat_id)
        return True
        
    elif registration_step == 'position':
        # Шаг 3: Ввод должности
        if not validate_position(text):
            # Неверная должность - показываем ошибку в существующем меню
            registration_handled = await handle_media_in_existing_menu(update, chat_id, "❌ неверный формат должности")
            if not registration_handled:
                logger.warning(f"Неверная должность, но активное меню не найдено для пользователя {chat_id}. Создаем сообщение регистрации.")
                
                sent_message = await update.get_bot().send_message(
                    chat_id=chat_id,
                    text="❌ **Неверный формат должности**\n\n"
                         "Пожалуйста, введите должность (от 2 до 50 символов)\n\n"
                         "Для отмены регистрации напишите: `сброс`",
                    parse_mode='Markdown'
                )
            return True
        
        # Проверяем валидность контекста
        if not validate_registration_context(context, 'position'):
            registration_handled = await handle_media_in_existing_menu(update, chat_id, "❌ ошибка в процессе регистрации")
            if not registration_handled:
                logger.warning(f"Ошибка регистрации, но активное меню не найдено для пользователя {chat_id}. Создаем сообщение с инструкциями.")
                
                sent_message = await update.get_bot().send_message(
                    chat_id=chat_id,
                    text="❌ **Ошибка в процессе регистрации**\n\n"
                         "Произошла ошибка в данных регистрации.\n"
                         "Начните регистрацию заново с команды `/start`",
                    parse_mode='Markdown'
                )
            # Очищаем поврежденные данные
            handle_user_registration.temp_storage.pop(chat_id, None)
            return True
        
        # Завершаем регистрацию
        context['position'] = text.strip()
        handle_user_registration.temp_storage[chat_id] = context
        await complete_registration_with_smart_menu(update, chat_id, context)
        return True
    
    # Неизвестный шаг - текст не обработан
    return False


async def show_region_selection_with_smart_menu(update: Update, chat_id: int):
    """
    Показывает выбор региона в существующем меню
    """
    # Пытаемся найти последнее активное меню
    from src.bot.utils import get_last_user_menu
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    bot = update.get_bot()
    last_menu = get_last_user_menu(chat_id)
    
    # Создаём клавиатуру с регионами
    groups = get_all_groups()
    keyboard = []
    for i, group in enumerate(groups):
        keyboard.append([InlineKeyboardButton(f"📍 {group}", callback_data=f"reg_select_group_{group}")])
        if i >= 10:  # Ограничиваем количество групп
            break
    
    text = (
        "**🏢 Выбор рабочих групп**\n\n"
        "Выберите группы складов, к которым у вас есть доступ:\n\n"
        "📋 **Доступные группы:**"
    )
    
    if last_menu and last_menu.get('message_id') and last_menu.get('chat_id'):
        try:
            await bot.edit_message_text(
                chat_id=last_menu.get('chat_id'),
                message_id=last_menu.get('message_id'),
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return
        except Exception as e:
            logger.error(f"Ошибка при редактировании меню для выбора региона: {e}")
    
    # Если не получилось отредактировать, создаём новое
    await reply_with_keyboard(
        update,
        text,
        custom_keyboard=InlineKeyboardMarkup(keyboard),
        is_registration=True
    )


async def complete_registration_with_smart_menu(update: Update, chat_id: int, context: dict):
    """
    Завершает регистрацию в существующем меню
    """
    await complete_registration(update, chat_id, context)


async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик неизвестных команд (начинающихся с /)
    """
    chat_id = update.effective_chat.id
    command = update.message.text.strip()
    
    logger.info(f"Неизвестная команда от {chat_id}: {command}")
    
    # Удаляем сообщение с командой
    try:
        await update.message.delete()
        logger.info(f"Удалена неизвестная команда ({command}) от {chat_id}")
    except Exception as e:
        logger.warning(f"Не удалось удалить неизвестную команду: {e}")
    
    # Используем универсальную систему умного обновления
    from src.bot.utils import smart_update_current_menu
    
    command_handled = await smart_update_current_menu(
        update, 
        chat_id, 
        "Неизвестная команда", 
        f"/{command.lstrip('/')}"
    )
    
    if not command_handled:
        # Если не нашли активное меню, создаем главное меню с ошибкой
        logger.warning(f"Неизвестная команда {command}, но активное меню не найдено для пользователя {chat_id}. Создаем главное меню.")
        
        from src.core.auth import get_user_role
        from src.bot.keyboards import get_main_keyboard
        
        role = get_user_role(chat_id)
        keyboard = get_main_keyboard(role)
        
        # Создаем главное меню с сообщением об ошибке
        sent_message = await update.get_bot().send_message(
            chat_id=chat_id,
            text=f"❌ **Неизвестная команда**\n\n"
                 f"Команда: `{command}`\n\n"
                 f"Доступные команды: /start, /help\n"
                 f"Используйте кнопки меню для навигации.",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # ВАЖНО: Регистрируем созданное главное меню для отслеживания
        if sent_message:
            from src.bot.utils import track_user_menu
            track_user_menu(
                user_id=chat_id, 
                chat_id=chat_id, 
                message_id=sent_message.message_id, 
                menu_type="main",
                menu_context={}
            )