"""
Обработчики регистрации пользователей
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.config.logging import SecureLogger
from src.core.registration_manager import registration_manager
from src.core.storage import AdminManager
from src.core.auth import get_user_role
from src.bot.keyboards import get_registration_groups_keyboard, get_main_keyboard
from src.bot.utils import send_message_with_persistent_keyboard

logger = SecureLogger(__name__)


class RegistrationHandler:
    """Обработчик процесса регистрации пользователей"""
    
    @staticmethod
    async def start_registration(update: Update, chat_id: int):
        """Начинает процесс регистрации нового пользователя"""
        registration_manager.start_registration(chat_id)
        
        welcome_text = (
            "👋 **Добро пожаловать в CelsiusPulse Bot!**\n\n"
            "Для доступа к системе мониторинга температуры необходимо пройти регистрацию.\n\n"
            "🔹 **Шаг 1/3: Введите ваше ФИО**\n\n"
            "📋 **Требования:**\n"
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
            "• Макиавелли Никколо Ди Бернардо Деи"
        )
        
        await send_message_with_persistent_keyboard(
            update, 
            welcome_text, 
            parse_mode='Markdown',
            is_registration=True
        )
    
    @staticmethod
    async def show_group_selection(update: Update, chat_id: int):
        """Показывает выбор групп (шаг 2 регистрации)"""
        state = registration_manager.get_registration_state(chat_id)
        if not state or not state.fio:
            await RegistrationHandler.start_registration(update, chat_id)
            return
        
        # Получаем все доступные группы из системы мониторинга
        from src.core.monitoring import get_all_groups
        available_groups = get_all_groups()
        
        if not available_groups:
            error_text = (
                "❌ **Ошибка конфигурации**\n\n"
                "Группы пользователей не настроены в системе. "
                "Обратитесь к администратору."
            )
            await update.message.reply_text(error_text, parse_mode='Markdown')
            registration_manager.clear_registration(chat_id)
            return
        
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
        
        try:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(
                    groups_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    groups_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Ошибка отправки выбора групп: {e}")
            await update.message.reply_text(
                "Ошибка отображения групп. Попробуйте снова.",
                parse_mode='Markdown'
            )
    
    @staticmethod
    async def handle_group_toggle(update: Update, chat_id: int, group: str):
        """Обрабатывает переключение выбора группы"""
        query = update.callback_query
        
        # Переключаем группу
        is_added = registration_manager.toggle_group(chat_id, group)
        
        # Обновляем отображение
        await RegistrationHandler.show_group_selection(update, chat_id)
        
        # Показываем уведомление
        action = "добавлена" if is_added else "убрана"
        await query.answer(f"Группа {group} {action}", show_alert=False)
    
    @staticmethod
    async def handle_finish_group_selection(update: Update, chat_id: int):
        """Завершает выбор групп и переходит к должности"""
        state = registration_manager.get_registration_state(chat_id)
        
        if not state or not state.selected_groups:
            await update.callback_query.answer(
                "❌ Выберите минимум одну группу", 
                show_alert=True
            )
            return
        
        # Переходим к следующему шагу
        if registration_manager.finish_group_selection(chat_id):
            position_text = (
                f"✅ **ФИО:** `{state.fio}`\n"
                f"✅ **Группы:** {', '.join(state.selected_groups)}\n\n"
                "🔹 **Шаг 3/3: Введите вашу должность**\n\n"
                "📋 **Требования:**\n"
                "• Минимум 2 символа\n"
                "• Укажите реальную должность"
            )
            
            await update.callback_query.edit_message_text(
                position_text,
                parse_mode='Markdown'
            )
        else:
            await update.callback_query.answer(
                "❌ Ошибка при переходе к следующему шагу",
                show_alert=True
            )
    
    @staticmethod
    async def complete_registration(update: Update, chat_id: int):
        """Завершает процесс регистрации"""
        registration_data = registration_manager.get_registration_data(chat_id)
        
        if not registration_data:
            await update.message.reply_text(
                "❌ Ошибка завершения регистрации. Попробуйте снова."
            )
            registration_manager.clear_registration(chat_id)
            return
        
        # Сохраняем данные пользователя
        success = AdminManager.save_admin_info(
            chat_id,
            registration_data['fio'],
            registration_data['position'],
            role="admin",  # Новые пользователи получают роль admin
            groups=registration_data['groups']
        )
        
        if success:
            # Очищаем состояние регистрации
            registration_manager.clear_registration(chat_id)
            
            # Определяем роль пользователя
            role = get_user_role(chat_id)
            
            success_text = (
                "🎉 **Регистрация завершена успешно!**\n\n"
                f"👤 **ФИО:** {registration_data['fio']}\n"
                f"💼 **Должность:** {registration_data['position']}\n"
                f"🏢 **Группы:** {', '.join(registration_data['groups'])}\n"
                f"🔐 **Роль:** {role}\n\n"
                "✅ Теперь вам доступны все функции системы мониторинга температуры.\n\n"
                "📱 Используйте кнопки меню для навигации:"
            )
            
            keyboard = get_main_keyboard(role)
            
            await update.message.reply_text(
                success_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка сохранения данных регистрации. Попробуйте снова."
            )
            registration_manager.clear_registration(chat_id)
    
    @staticmethod
    async def handle_registration_reset(update: Update, chat_id: int, text: str):
        """Обрабатывает команды сброса регистрации"""
        registration_manager.clear_registration(chat_id)
        
        # Удаляем сообщение команды сброса
        try:
            await update.message.delete()
            logger.info(f"Удалено сообщение сброса регистрации от {chat_id}: {text}")
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение сброса: {e}")
        
        reset_text = (
            "🔄 **Регистрация сброшена**\n\n"
            "Процесс регистрации был отменен. Начинаем заново!\n\n"
        )
        
        await update.message.reply_text(reset_text, parse_mode='Markdown')
        
        # Сразу начинаем новую регистрацию
        await RegistrationHandler.start_registration(update, chat_id)


# Экспортируем для совместимости
handle_user_registration = RegistrationHandler.start_registration