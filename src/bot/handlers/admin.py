"""
Обработчики административных функций и текстового ввода
"""
import re
from telegram import Update
from telegram.ext import ContextTypes
from ...config.logging import SecureLogger
from ...core.auth import get_user_role, add_user_to_group, update_env_file
from ...core.storage import AdminManager
from ...core.monitoring import get_all_groups
from ...bot.messages import format_welcome_message, format_error_message
from ...bot.keyboards import get_main_keyboard
from ...utils.security import validate_request_security
from ...utils.validators import validate_user_input

logger = SecureLogger(__name__)


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик текстовых сообщений (регистрация пользователей)
    """
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    # Проверка безопасности
    is_safe, error_msg = validate_request_security(chat_id, text)
    if not is_safe:
        await update.message.reply_text(format_error_message('rate_limited', error_msg))
        return
    
    # Валидация входных данных
    if not validate_user_input(text):
        await update.message.reply_text(
            format_error_message('invalid_input', 'Содержит недопустимые символы')
        )
        return
    
    logger.info(f"Текстовое сообщение от {chat_id}: {len(text)} символов")
    
    try:
        # Проверяем, не обрабатывается ли ввод пороговых значений
        threshold_handled = await handle_threshold_input(update, text, chat_id)
        if threshold_handled:
            return
        
        # Проверяем, зарегистрирован ли пользователь
        admin_info = AdminManager.load_admin_info(chat_id)
        
        if not admin_info or 'fio' not in admin_info:
            # Проверяем команду сброса регистрации ТОЛЬКО для незарегистрированных
            if text.lower().strip() in ['сброс', 'reset', 'отмена', 'cancel']:
                await handle_registration_reset(update, chat_id)
                return
            
            # Новый пользователь - обрабатываем регистрацию
            await handle_user_registration(update, text, chat_id)
        else:
            # Существующий пользователь - неизвестная команда
            await update.message.reply_text(
                "❓ Неизвестная команда. Используйте меню для навигации."
            )
    
    except Exception as e:
        logger.error(f"Ошибка обработки текста от {chat_id}: {e}")
        await update.message.reply_text(
            format_error_message('system_error', 'Ошибка при обработке сообщения')
        )


async def handle_user_registration(update: Update, text: str, chat_id: int):
    """
    Обработка многошаговой регистрации нового пользователя
    """
    # Получаем контекст через context.user_data
    context = update.callback_query.get_bot().application.user_data.get(chat_id, {}) if hasattr(update, 'callback_query') and update.callback_query else {}
    if not context:
        # Используем временное хранение состояния
        if not hasattr(handle_user_registration, 'temp_storage'):
            handle_user_registration.temp_storage = {}
        context = handle_user_registration.temp_storage.get(chat_id, {})
    registration_step = context.get('registration_step', 'fio')
    
    logger.info(f"Регистрация пользователя {chat_id}, шаг: {registration_step}")
    
    if registration_step == 'fio':
        # Шаг 1: Ввод ФИО
        if not validate_fio(text):
            await update.message.reply_text(
                "❌ **Неверный формат ФИО**\n\n"
                "Укажите полное ФИО корректно:\n\n"
                "📅 **Требования:**\n"
                "• 3-5 слов (Фамилия Имя Отчество)\n"
                "• Каждое слово от 2 до 15 символов\n"
                "• Только буквы русского/английского алфавита\n"
                "• Каждое слово начинается с заглавной буквы\n"
                "• Не тестовые данные и не бессмыслица\n\n"
                "📝 **Примеры:**\n"
                "• Пушкин Александр Сергеевич\n"
                "• Салтыков-Щедрин Михаил Евграфович\n"
                "• Гюго Виктор-Мари Жозефович\n"
                "• Толкин Джон Рональд Руэл\n"
                "• Макиавелли Никколо Ди Бернардо Деи\n",
                parse_mode='Markdown'
            )
            return
        
        # Сохраняем ФИО и переходим к выбору региона
        context['fio'] = text.strip()
        context['registration_step'] = 'region'
        context['selected_groups'] = []  # Инициализируем список выбранных групп
        # Сохраняем в временное хранилище
        if not hasattr(handle_user_registration, 'temp_storage'):
            handle_user_registration.temp_storage = {}
        handle_user_registration.temp_storage[chat_id] = context
        
        # Показываем список регионов
        await show_region_selection(update, chat_id)
        
    elif registration_step == 'position':
        # Шаг 3: Ввод должности
        if not validate_position(text):
            await update.message.reply_text(
                "❌ **Неверный формат должности**\n\n"
                "📅 **Требования:**\n"
                "• От 2 до 50 символов\n"
                "• 1-4 осмысленных слова\n"
                "• Только буквы, цифры, пробелы, дефисы, точки, скобки\n"
                "• Не тестовые данные и не бессмыслица\n\n"
                "📝 **Примеры корректных должностей:**\n"
                "• Директор\n"
                "• Заместитель директора\n"
                "• Региональный руководитель\n"
                "• Бригадир\n\n"
                "📝 Введите должность заново:",
                parse_mode='Markdown'
            )
            return
        
        # Проверяем валидность контекста
        if not validate_registration_context(context, 'position'):
            await update.message.reply_text(
                "❌ **Ошибка в процессе регистрации**\n\n"
                "Данные повреждены. Начните регистрацию заново с команды /start",
                parse_mode='Markdown'
            )
            # Очищаем поврежденные данные
            if hasattr(handle_user_registration, 'temp_storage'):
                handle_user_registration.temp_storage.pop(chat_id, None)
            return
        
        # Завершаем регистрацию
        context['position'] = text.strip()
        handle_user_registration.temp_storage[chat_id] = context
        await complete_registration(update, chat_id, context)
    
    else:
        await update.message.reply_text(
            "❓ Неизвестное состояние регистрации. Начните с /start"
        )


async def handle_registration_reset(update: Update, chat_id: int):
    """
    Обрабатывает сброс регистрации пользователя
    """
    logger.info(f"Сброс регистрации для пользователя {chat_id}")
    
    # Очищаем данные регистрации
    if hasattr(handle_user_registration, 'temp_storage'):
        handle_user_registration.temp_storage.pop(chat_id, None)
    
    # Показываем сообщение о сбросе и начинаем заново
    from ...bot.messages import format_welcome_message
    
    await update.message.reply_text(
        "🔄 **Регистрация сброшена**\n\n"
        "Все данные очищены. Начинаем регистрацию заново:",
        parse_mode='Markdown'
    )
    
    # Показываем приветственное сообщение
    welcome_message = format_welcome_message(is_new_user=True, chat_id=chat_id)
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def show_region_selection(update: Update, chat_id: int):
    """
    Показывает список регионов для выбора с поддержкой множественного выбора
    """
    from ...core.monitoring import get_all_groups
    from ...bot.keyboards import get_registration_groups_keyboard
    
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
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )


async def complete_registration(update: Update, chat_id: int, context: dict):
    """
    Завершает процесс регистрации и отправляет подтверждение big_boss
    """
    fio = context.get('fio')
    selected_groups = context.get('selected_groups', [])
    position = context.get('position')
    
    logger.info(f"Завершение регистрации пользователя {chat_id}: {fio}")
    
    try:
        # НЕ СОХРАНЯЕМ данные до подтверждения! Только отправляем запрос
        await send_registration_request_to_big_boss(update, chat_id, fio, selected_groups, position)
        
        # Уведомляем пользователя
        groups_text = ', '.join(selected_groups) if selected_groups else 'Не выбраны'
        await update.message.reply_text(
            "✅ **Регистрация завершена!**\n\n"
            f"👤 ФИО: {fio}\n"
            f"🗺️ Регион(ы): {groups_text}\n"
            f"💼 Должность: {position}\n\n"
            "⏳ Ваш запрос отправлен на рассмотрение администратору.\n"
            "Вы получите уведомление о решении.",
            parse_mode='Markdown'
        )
        
        # Очищаем состояние регистрации
        if hasattr(handle_user_registration, 'temp_storage'):
            handle_user_registration.temp_storage.pop(chat_id, None)
    
    except Exception as e:
        logger.error(f"Ошибка при завершении регистрации {chat_id}: {e}")
        await update.message.reply_text(
            format_error_message('system_error', 'Ошибка при завершении регистрации')
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


def validate_fio(fio: str) -> bool:
    """
    Усиленная валидация ФИО с защитой от бессмысленных данных
    """
    if not fio or not isinstance(fio, str):
        return False
    
    fio = fio.strip()
    
    # Проверка длины
    if len(fio) < 5 or len(fio) > 100:
        return False
    
    # Проверка на подозрительные паттерны
    fio_lower = fio.lower()
    
    # Запрещенные паттерны (тест, спам, бессмыслица)
    suspicious_patterns = [
        r'test', r'тест', r'spam', r'спам', r'fake', r'фейк',
        r'admin', r'администратор', r'root', r'user', r'юзер',
        r'qwerty', r'asdf', r'123', r'111', r'000',
        r'aaa+', r'ааа+', r'xxx', r'ыыы+',  # Повторяющиеся символы
        r'([a-zа-я])\1{3,}',  # 4+ одинаковых символа подряд
        r'^[a-zа-я]{1,2}\s[a-zа-я]{1,2}\s[a-zа-я]{1,2}$'  # Слишком короткие части
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, fio_lower):
            return False
    
    words = fio.split()
    
    # Поддержка 3-5 слов (Фамилия Имя Отчество [Второе имя] [Приставка])
    if len(words) < 3 or len(words) > 5:
        return False
    
    # Валидация каждого слова
    for i, word in enumerate(words):
        if not word or len(word) < 2 or len(word) > 15:
            return False
        
        # Только буквы, дефисы и апострофы
        if not re.match(r'^[А-Яа-яЁёA-Za-z\-\']+$', word):
            return False
        
        # Каждое слово должно начинаться с заглавной буквы
        if not word[0].isupper():
            return False
        
        # Слово не должно состоять только из дефисов/апострофов
        if word.replace('-', '').replace("'", '') == '':
            return False
        
        # Первые 3 слова должны быть достаточно длинными
        if i < 3 and len(word) < 2:
            return False
        
        # Проверка на повторяющиеся символы в слове
        if re.search(r'([а-яё])\1{2,}', word.lower()) or re.search(r'([a-z])\1{2,}', word.lower()):
            return False
    
    # Проверяем, что первые 3 слова различаются
    if len(set(w.lower() for w in words[:3])) < 3:
        return False
    
    # Проверяем правдоподобность (не все слова одинаковой длины)
    word_lengths = [len(w) for w in words]
    if len(set(word_lengths)) == 1 and len(words) >= 3:
        return False
    
    return True


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
    Обработка ввода пороговых значений
    
    Returns:
        True если ввод был обработан как пороговые значения
    """
    from ...bot.handlers.callbacks import handle_set_threshold_device
    from ...core.storage import ThresholdManager
    from ...core.auth import can_access_group
    
    # Проверяем, есть ли контекст для пороговых значений
    temp_storage = getattr(handle_set_threshold_device, 'temp_storage', {})
    context = temp_storage.get(chat_id)
    
    if not context:
        return False
    
    action = context.get('action')
    group_name = context.get('group_name')
    device_id = context.get('device_id')
    
    if not action or not group_name:
        return False
    
    # Проверяем доступ к группе
    if not can_access_group(chat_id, group_name):
        await update.message.reply_text("❌ Нет доступа к этой группе")
        # Очищаем контекст
        temp_storage.pop(chat_id, None)
        return True
    
    # Парсим пороговые значения в формате "мин макс"
    try:
        parts = text.strip().split()
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ Неверный формат. Используйте: `мин макс`\n"
                "Например: `18 25`",
                parse_mode='Markdown'
            )
            return True
        
        min_temp = float(parts[0])
        max_temp = float(parts[1])
        
        if min_temp >= max_temp:
            await update.message.reply_text("❌ Минимальная температура должна быть меньше максимальной")
            return True
        
        if min_temp < -50 or max_temp > 100:
            await update.message.reply_text("❌ Температуры должны быть в диапазоне от -50°C до 100°C")
            return True
        
        # Сохраняем пороговые значения
        success = False
        
        if action == 'set_threshold_group' and device_id == 'ALL':
            # Устанавливаем пороги для всей группы
            from ...core.monitoring import get_sensors_by_group
            sensors = get_sensors_by_group(group_name)
            success_count = 0
            
            for sensor in sensors:
                sensor_device_id = sensor['device_id']
                if ThresholdManager.set_device_threshold(sensor_device_id, group_name, min_temp, max_temp):
                    success_count += 1
            
            success = success_count > 0
            
            if success:
                await update.message.reply_text(
                    f"✅ **Пороговые значения установлены для группы {group_name}**\n\n"
                    f"🌡️ Минимум: {min_temp}°C\n"
                    f"🌡️ Максимум: {max_temp}°C\n"
                    f"📊 Обновлено устройств: {success_count}/{len(sensors)}"
                )
            else:
                await update.message.reply_text("❌ Ошибка при сохранении пороговых значений")
            
        elif action == 'set_threshold_device':
            # Устанавливаем пороги для конкретного устройства
            success = ThresholdManager.set_device_threshold(device_id, group_name, min_temp, max_temp)
            
            if success:
                await update.message.reply_text(
                    f"✅ **Пороговые значения установлены для {device_id}**\n\n"
                    f"🏢 Группа: {group_name}\n"
                    f"🌡️ Минимум: {min_temp}°C\n"
                    f"🌡️ Максимум: {max_temp}°C"
                )
            else:
                await update.message.reply_text("❌ Ошибка при сохранении пороговых значений")
        
        # Очищаем контекст
        temp_storage.pop(chat_id, None)
        
        logger.info(f"Пороговые значения обновлены пользователем {chat_id}: {group_name}/{device_id} = {min_temp}-{max_temp}")
        return True
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неверные числовые значения. Используйте: `мин макс`\n"
            "Например: `18.5 25.0`",
            parse_mode='Markdown'
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка обработки пороговых значений от {chat_id}: {e}")
        await update.message.reply_text("❌ Ошибка при обработке пороговых значений")
        # Очищаем контекст при ошибке
        temp_storage.pop(chat_id, None)
        return True