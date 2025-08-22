"""
Обработчики основных команд бота
"""
from telegram import Update
from telegram.ext import ContextTypes
from src.config.logging import SecureLogger
from src.core.auth import get_user_role, is_authorized
from src.core.storage import AdminManager
from src.bot.messages import format_welcome_message, format_error_message
from src.bot.keyboards import get_main_keyboard, get_quick_main_keyboard
from src.bot.utils import reply_with_keyboard
from src.utils.security import validate_request_security

logger = SecureLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /start
    Приветствие и отображение главного меню
    """
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Проверка безопасности
    is_safe, error_msg = validate_request_security(chat_id, "/start")
    if not is_safe:
        await reply_with_keyboard(update, format_error_message('rate_limited', error_msg))
        return
    
    logger.info(f"Обработка команды /start для {chat_id}")
    
    # Очищаем контекст пороговых значений при команде /start
    from src.bot.handlers.callbacks import clear_threshold_context
    clear_threshold_context(user.id)
    
    try:
        # Определяем роль пользователя
        role = get_user_role(chat_id)
        
        # Проверяем, зарегистрирован ли пользователь
        admin_info = AdminManager.load_admin_info(chat_id)
        
        if not admin_info or 'fio' not in admin_info:
            # Проверяем, не находится ли пользователь уже в процессе регистрации
            from src.bot.handlers.registration_handlers import registration_manager
            existing_context = registration_manager.get_registration_data(chat_id) or {}
            if existing_context.get('step'):
                current_step = existing_context.get('step')
                
                if current_step == 'fio':
                    await update.message.reply_text(
                        "⚠️ Регистрация уже в процессе\n\n"
                        "Введите полное ФИО в формате: Иванов Иван Иванович",
                        parse_mode='Markdown'
                    )
                
                elif current_step == 'groups':
                    # Повторно показываем список регионов с учетом уже выбранных
                    from src.core.monitoring import get_all_groups
                    from src.bot.keyboards import get_registration_groups_keyboard
                    
                    available_groups = get_all_groups()
                    selected_groups = existing_context.get('selected_groups', [])
                    keyboard = get_registration_groups_keyboard(available_groups, selected_groups)
                    
                    message_text = "⚠️ Регистрация уже в процессе\n\n"
                    message_text += f"👤 ФИО: {existing_context.get('fio', 'Неизвестно')}\n\n"
                    message_text += "🗺️ Выберите регион(ы):\n\n"
                    if selected_groups:
                        message_text += f"✅ Уже выбрано: {', '.join(selected_groups)}\n\n"
                    message_text += "💡 Для сброса напишите: сброс"
                    
                    await update.message.reply_text(
                        message_text,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                
                elif current_step == 'position':
                    selected_groups = existing_context.get('selected_groups', [])
                    groups_text = ', '.join(selected_groups) if selected_groups else 'Неизвестно'
                    
                    await update.message.reply_text(
                        "⚠️ Регистрация уже в процессе\n\n"
                        f"👤 ФИО: {existing_context.get('fio', 'Неизвестно')}\n"
                        f"🗺️ Регион(ы): {groups_text}\n\n"
                        "💼 Введите должность:",
                        parse_mode='Markdown'
                    )
                
                else:
                    await update.message.reply_text(
                        "⚠️ Регистрация уже в процессе\n\n"
                        "Завершите текущий шаг регистрации.",
                        parse_mode='Markdown'
                    )
                
                return
            
            # Новый пользователь - показываем форму регистрации БЕЗ кнопки главного меню
            logger.info(f"Новый пользователь: {chat_id}")
            welcome_message = format_welcome_message(is_new_user=True, chat_id=chat_id)
            await update.message.reply_text(welcome_message, parse_mode='Markdown')
        else:
            # Существующий пользователь - показываем главное меню
            fio = admin_info.get('fio', '')
            position = admin_info.get('position', '')
            
            welcome_message = format_welcome_message(fio, position, is_new_user=False)
            keyboard = get_main_keyboard(role)
            
            # Отправляем главное меню без дублирования
            sent_message = await update.message.reply_text(
                welcome_message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            # ВАЖНО: Отслеживаем главное меню для системы умного обновления
            if sent_message:
                from src.bot.utils import track_user_menu
                track_user_menu(
                    user_id=chat_id, 
                    chat_id=chat_id, 
                    message_id=sent_message.message_id, 
                    menu_type="main",
                    menu_context={}
                )
    
    except Exception as e:
        logger.error(f"Ошибка в команде /start для {chat_id}: {e}")
        await reply_with_keyboard(
            update,
            format_error_message('system_error', 'Ошибка при обработке команды')
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /help
    Показывает справочную информацию
    """
    chat_id = update.effective_chat.id
    
    # Проверка безопасности
    is_safe, error_msg = validate_request_security(chat_id, "/help")
    if not is_safe:
        await reply_with_keyboard(update, format_error_message('rate_limited', error_msg))
        return
    
    logger.info(f"Обработка команды /help для {chat_id}")
    
    # Очищаем контекст пороговых значений при команде /help
    from src.bot.handlers.callbacks import clear_threshold_context
    user = update.effective_user
    clear_threshold_context(user.id)
    
    try:
        role = get_user_role(chat_id)
        
        help_text = """
🌡️ CelsiusPulse Bot - Справка

Основные функции:
• 📊 Просмотр данных температуры
• 🔔 Получение уведомлений о критических значениях
• 📈 Мониторинг по группам складских помещений

Команды:
• /start - Главное меню
• /help - Эта справка

Навигация:
Используйте кнопки меню для навигации по системе.
        """
        
        if role in ['admin', 'big_boss']:
            help_text += """
Административные функции:
• ⚙️ Управление пороговыми значениями
• 👥 Просмотр всех пользователей
• 📊 Системная статистика
            """
        
        if role == 'big_boss':
            help_text += """
Функции руководителя:
• 🔐 Мониторинг безопасности
• 👥 Управление администраторами
• 🛠️ Системные настройки
            """
        
        help_text += """
📞 Поддержка: Обратитесь к системному администратору
        """
        
        await reply_with_keyboard(update, help_text, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Ошибка в команде /help для {chat_id}: {e}")
        await reply_with_keyboard(
            update,
            format_error_message('system_error', 'Ошибка при получении справки')
        )