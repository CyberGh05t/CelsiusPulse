"""
Обработчики различных типов входных данных
"""
from telegram import Update
from telegram.ext import ContextTypes
from src.config.logging import SecureLogger
from src.core.registration_manager import registration_manager
from src.core.threshold_context_manager import threshold_context_manager
from src.utils.validators import validate_user_input, validate_fio
from src.utils.security import validate_request_security, detect_invalid_content
from src.bot.utils import smart_update_current_menu

logger = SecureLogger(__name__)


class InputHandler:
    """Централизованный обработчик входных данных"""
    
    @staticmethod
    async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик текстовых сообщений с полным умным удалением
        ВСЕ неподходящие текстовые сообщения удаляются и обрабатываются через систему умного удаления
        """
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        
        # Проверяем на наличие невалидного контента (ссылки, спам, etc.)
        invalid_content_type = detect_invalid_content(text)
        if invalid_content_type:
            await InputHandler._handle_invalid_content(update, chat_id, text, invalid_content_type)
            return
        
        # Проверка безопасности с умным удалением
        is_safe, error_msg = validate_request_security(chat_id, text)
        if not is_safe:
            await InputHandler._handle_invalid_content(update, chat_id, text, "⚠️ ограничение безопасности")
            return
        
        # Валидация входных данных с умным удалением
        if not validate_user_input(text):
            await InputHandler._handle_invalid_content(update, chat_id, text, "❌ недопустимые символы")
            return
        
        logger.info(f"Текстовое сообщение от {chat_id}: {len(text)} символов")
        
        try:
            # ПРИОРИТЕТ 1: Проверяем ввод пороговых значений (единственный валидный случай)
            threshold_handled = await InputHandler._handle_threshold_input(update, text, chat_id)
            if threshold_handled:
                return
            
            # ПРИОРИТЕТ 2: Проверяем процесс регистрации
            if registration_manager.is_in_registration(chat_id):
                await InputHandler._handle_registration_input(update, text, chat_id)
                return
            
            # ПРИОРИТЕТ 3: Все остальные текстовые сообщения = невалидный контент
            await InputHandler._handle_invalid_content(update, chat_id, text, "📝 произвольный текст")
        
        except Exception as e:
            logger.error(f"Ошибка обработки текста от {chat_id}: {e}")
            await InputHandler._handle_invalid_content(update, chat_id, text, "💥 системная ошибка")
    
    @staticmethod
    async def _handle_threshold_input(update: Update, text: str, chat_id: int) -> bool:
        """
        Обрабатывает ввод пороговых значений
        
        Returns:
            True если ввод был обработан как пороговые значения
        """
        user_id = update.effective_user.id
        context = threshold_context_manager.get_context(user_id)
        
        if not context:
            return False
        
        # Валидируем формат "мин макс"
        parts = text.strip().split()
        if len(parts) != 2:
            await InputHandler._handle_invalid_content(
                update, chat_id, text, "❌ неверный формат (нужно: мин макс)"
            )
            return True
        
        try:
            min_temp = float(parts[0])
            max_temp = float(parts[1])
            
            if min_temp >= max_temp:
                await InputHandler._handle_invalid_content(
                    update, chat_id, text, "❌ минимум должен быть меньше максимума"
                )
                return True
            
            if min_temp < -50 or max_temp > 100:
                await InputHandler._handle_invalid_content(
                    update, chat_id, text, "❌ значения вне допустимого диапазона (-50°C до 100°C)"
                )
                return True
            
            # Сохраняем пороговые значения
            from src.core.storage import ThresholdManager
            success = await ThresholdManager.save_thresholds_async(
                context.group_name, context.device_id, min_temp, max_temp
            )
            
            if success:
                # Удаляем исходное сообщение пользователя
                try:
                    await update.message.delete()
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение с порогами: {e}")
                
                # Обновляем меню с подтверждением
                success_text = f"✅ **Пороговые значения обновлены**\n\n"
                if context.device_id == "ALL":
                    success_text += f"🏢 Группа: {context.group_name}\n"
                else:
                    success_text += f"🌡️ Устройство: {context.device_id}\n🏢 Группа: {context.group_name}\n"
                success_text += f"🌡️ Минимум: {min_temp}°C\n🌡️ Максимум: {max_temp}°C"
                
                # Отправляем подтверждение через умное обновление
                await smart_update_current_menu(
                    update, user_id, success_text, "✅ успешное обновление"
                )
                
                # Очищаем контекст
                threshold_context_manager.clear_context(user_id)
            else:
                await InputHandler._handle_invalid_content(
                    update, chat_id, text, "💥 ошибка сохранения"
                )
            
            return True
            
        except ValueError:
            await InputHandler._handle_invalid_content(
                update, chat_id, text, "❌ значения должны быть числами"
            )
            return True
    
    @staticmethod
    async def _handle_registration_input(update: Update, text: str, chat_id: int):
        """Обрабатывает ввод во время регистрации"""
        step = registration_manager.get_registration_step(chat_id)
        
        if step == 'fio':
            if not validate_fio(text):
                error_msg = (
                    "❌ **Неверный формат ФИО**\n\n"
                    "Укажите полное ФИО корректно:\n\n"
                    "📅 **Требования:**\n"
                    "• 3-5 слов (Фамилия Имя Отчество)\n"
                    "• Каждое слово от 2 до 15 символов\n"
                    "• Только буквы русского/английского алфавита\n"
                    "• Каждое слово начинается с заглавной буквы\n\n"
                    "📝 **Примеры:**\n"
                    "• Пушкин Александр Сергеевич\n"
                    "• Салтыков-Щедрин Михаил Евграфович"
                )
                await update.message.reply_text(error_msg, parse_mode='Markdown')
                return
            
            # Обновляем ФИО и переходим к следующему шагу
            if registration_manager.update_fio(chat_id, text):
                from src.bot.handlers.registration_handlers import RegistrationHandler
                await RegistrationHandler.show_group_selection(update, chat_id)
        
        elif step == 'position':
            if len(text.strip()) < 2:
                error_msg = (
                    "❌ **Неверный формат должности**\n\n"
                    "Введите вашу должность (минимум 2 символа)\n"
                    "Например: Директор, Заместитель директора, Менеджер"
                )
                await update.message.reply_text(error_msg, parse_mode='Markdown')
                return
            
            # Завершаем регистрацию
            if registration_manager.update_position(chat_id, text.strip()):
                from src.bot.handlers.registration_handlers import RegistrationHandler
                await RegistrationHandler.complete_registration(update, chat_id)
    
    @staticmethod
    async def _handle_invalid_content(update: Update, chat_id: int, _text: str, content_type: str):
        """
        Обрабатывает невалидный контент с универсальным умным обновлением меню
        """
        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
            logger.info(f"Удалено сообщение с невалидным контентом ({content_type}) от {chat_id}")
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение с невалидным контентом: {e}")
        
        # Используем универсальную систему умного обновления
        content_handled = await smart_update_current_menu(
            update, 
            chat_id, 
            "Неподдерживаемый тип сообщения", 
            content_type
        )
        
        if not content_handled:
            # Если не нашли активное меню, создаем главное меню с ошибкой
            logger.warning(f"Контент удален, но активное меню не найдено для пользователя {chat_id}")
            from src.bot.keyboards import get_main_keyboard
            from src.core.auth import get_user_role
            
            role = get_user_role(chat_id)
            keyboard = get_main_keyboard(role)
            
            error_message = f"❌ **Неподдерживаемый тип сообщения**\n\nОбнаружен: {content_type}\n\nИспользуйте кнопки для навигации."
            
            try:
                await update.message.reply_text(
                    error_message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение об ошибке: {e}")


# Экспортируем основную функцию для совместимости
handle_text_input = InputHandler.handle_text_input