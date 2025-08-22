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
            # ПРИОРИТЕТ 1: Проверяем статус пользователя
            from src.core.auth import get_user_role
            role = get_user_role(chat_id)
            
            # ПРИОРИТЕТ 2: Если пользователь не зарегистрирован, обрабатываем как регистрационный ввод
            if role == "unregistered":
                # Проверяем, находится ли в процессе регистрации
                if registration_manager.is_in_registration(chat_id):
                    await InputHandler._handle_registration_input(update, text, chat_id)
                    return
                else:
                    # Начинаем процесс регистрации с введенного текста как ФИО
                    await InputHandler._handle_registration_input(update, text, chat_id)
                    return
            
            # ПРИОРИТЕТ 3: Для зарегистрированных пользователей - проверяем ввод пороговых значений
            threshold_handled = await InputHandler._handle_threshold_input(update, text, chat_id)
            if threshold_handled:
                return
            
            # ПРИОРИТЕТ 4: Все остальные текстовые сообщения от зарегистрированных пользователей = невалидный контент
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
            
            # Проверяем тип операции
            if context.action == 'set_threshold_user_sensors':
                # ОПТИМИЗИРОВАННАЯ массовая установка для всех групп пользователя
                from src.core.auth import get_user_accessible_groups
                from src.core.monitoring import get_sensors_by_group
                
                user_groups = get_user_accessible_groups(chat_id)
                total_sensors = 0
                
                # ОПТИМИЗАЦИЯ: Загружаем пороги ОДИН раз для всех операций
                thresholds = ThresholdManager.load_thresholds()
                
                # Собираем все изменения в памяти
                for group in user_groups:
                    sensors = get_sensors_by_group(group)
                    total_sensors += len(sensors)
                    
                    # Создаем группу в thresholds если её нет
                    if group not in thresholds:
                        thresholds[group] = {}
                    
                    # Устанавливаем пороги для всех датчиков группы
                    for sensor in sensors:
                        sensor_device_id = sensor['device_id']
                        thresholds[group][sensor_device_id] = {
                            "min": min_temp,
                            "max": max_temp
                        }
                
                # ОПТИМИЗАЦИЯ: Сохраняем пороги ОДИН раз для всех изменений
                success = ThresholdManager.save_thresholds(thresholds)
                total_updated = total_sensors if success else 0
                
                # Сбрасываем кеш пороговых значений для обновления статистики в реальном времени
                if success:
                    from src.core.monitoring import invalidate_threshold_cache
                    invalidate_threshold_cache()
                
                success_text = f"🔧 **Пороговые значения установлены для всех ваших датчиков!**\n\n"
                success_text += f"🌡️ Минимум: {min_temp}°C\n"
                success_text += f"🌡️ Максимум: {max_temp}°C\n"
                success_text += f"📊 Обновлено датчиков: {total_updated}/{total_sensors}\n"
                success_text += f"📍 Затронуто групп: {', '.join(user_groups)} ({len(user_groups)})"
            
            elif context.action == 'set_threshold_all_sensors':
                # ОПТИМИЗИРОВАННАЯ массовая установка для ВСЕХ датчиков ВСЕХ групп (только big_boss)
                from src.core.monitoring import get_all_groups, get_sensors_by_group
                
                all_groups = get_all_groups()
                total_sensors = 0
                
                # ОПТИМИЗАЦИЯ: Загружаем пороги ОДИН раз для всех операций
                thresholds = ThresholdManager.load_thresholds()
                
                # Собираем все изменения в памяти
                for group in all_groups:
                    sensors = get_sensors_by_group(group)
                    total_sensors += len(sensors)
                    
                    # Создаем группу в thresholds если её нет
                    if group not in thresholds:
                        thresholds[group] = {}
                    
                    # Устанавливаем пороги для всех датчиков группы
                    for sensor in sensors:
                        sensor_device_id = sensor['device_id']
                        thresholds[group][sensor_device_id] = {
                            "min": min_temp,
                            "max": max_temp
                        }
                
                # ОПТИМИЗАЦИЯ: Сохраняем пороги ОДИН раз для всех изменений
                success = ThresholdManager.save_thresholds(thresholds)
                total_updated = total_sensors if success else 0
                
                # Сбрасываем кеш пороговых значений для обновления статистики в реальном времени
                if success:
                    from src.core.monitoring import invalidate_threshold_cache
                    invalidate_threshold_cache()
                
                success_text = f"🌍 **Пороговые значения установлены для ВСЕХ датчиков системы!**\n\n"
                success_text += f"🌡️ Минимум: {min_temp}°C\n"
                success_text += f"🌡️ Максимум: {max_temp}°C\n"
                success_text += f"📊 Обновлено датчиков: {total_updated}/{total_sensors}\n"
                success_text += f"📍 Затронуто групп: {', '.join(all_groups)} ({len(all_groups)})"
            
            elif context.action == 'set_threshold_group':
                # ОПТИМИЗИРОВАННАЯ установка порогов для ВСЕХ датчиков конкретной группы
                from src.core.monitoring import get_sensors_by_group
                
                group_sensors = get_sensors_by_group(context.group_name)
                
                # ОПТИМИЗАЦИЯ: Загружаем пороги ОДИН раз
                thresholds = ThresholdManager.load_thresholds()
                
                # Создаем группу в thresholds если её нет
                if context.group_name not in thresholds:
                    thresholds[context.group_name] = {}
                
                # Устанавливаем пороги для всех датчиков группы в памяти
                for sensor in group_sensors:
                    sensor_device_id = sensor['device_id']
                    thresholds[context.group_name][sensor_device_id] = {
                        "min": min_temp,
                        "max": max_temp
                    }
                
                # ОПТИМИЗАЦИЯ: Сохраняем пороги ОДИН раз
                success = ThresholdManager.save_thresholds(thresholds)
                total_updated = len(group_sensors) if success else 0
                
                success_text = f"✅ **Пороговые значения обновлены для группы {context.group_name}**\n\n"
                success_text += f"🌡️ Минимум: {min_temp}°C\n"
                success_text += f"🌡️ Максимум: {max_temp}°C\n"
                success_text += f"📊 Обновлено датчиков: {total_updated}/{len(group_sensors)}"
            
            else:
                # Установка порогов для одного конкретного датчика (set_threshold_device)
                success = ThresholdManager.set_device_threshold(
                    context.device_id, context.group_name, min_temp, max_temp
                )
                
                # Сбрасываем кеш пороговых значений для обновления статистики в реальном времени
                if success:
                    from src.core.monitoring import invalidate_threshold_cache
                    invalidate_threshold_cache()
                # Экранируем подчеркивания в device_id для Markdown
                safe_device_id = context.device_id.replace('_', '\\_')
                success_text = f"✅ **Пороговые значения обновлены**\n\n"
                success_text += f"🌡️ Устройство: {safe_device_id}\n"
                success_text += f"🏢 Группа: {context.group_name}\n"
                success_text += f"🌡️ Минимум: {min_temp}°C\n"
                success_text += f"🌡️ Максимум: {max_temp}°C"
            
            if success:
                # Удаляем исходное сообщение пользователя
                try:
                    await update.message.delete()
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение с порогами: {e}")
                
                # Сохраняем информацию для правильной кнопки "Назад" перед очисткой контекста
                user_id = update.effective_user.id
                back_callback = "settings_thresholds"  # по умолчанию
                
                if context.action == 'set_threshold_device':
                    back_callback = f"change_threshold_{context.group_name}"
                    back_text = "🔙 Назад к устройствам"
                elif context.action == 'set_threshold_group':
                    back_callback = f"change_threshold_{context.group_name}"
                    back_text = "🔙 Назад к устройствам"
                elif context.action in ['set_threshold_user_sensors', 'set_threshold_all_sensors']:
                    back_callback = "settings_thresholds"
                    back_text = "🔙 Назад к группам"
                else:
                    back_callback = "settings_thresholds"
                    back_text = "🔙 Назад к группам"
                
                # Добавляем кнопку "Назад" к сообщению об успехе
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                
                keyboard = [[InlineKeyboardButton(back_text, callback_data=back_callback)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Редактируем исходное меню пороговых значений напрямую
                try:
                    bot = update.get_bot()
                    await bot.edit_message_text(
                        chat_id=context.chat_id,
                        message_id=context.message_id,
                        text=success_text,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Не удалось обновить сообщение с успехом: {e}")
                    # Fallback: используем умное обновление
                    await smart_update_current_menu(
                        update, chat_id, success_text, "✅ успешное обновление"
                    )
                
                # Очищаем контекст после успешного обновления
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
        # Проверяем команду сброса ПЕРВЫМ делом
        if text.lower().strip() == "сброс":
            from src.bot.handlers.registration_handlers import RegistrationHandler
            await RegistrationHandler.handle_registration_reset(update, chat_id, text)
            return
            
        step = registration_manager.get_registration_step(chat_id)
        
        # Если пользователь не в процессе регистрации, начинаем с ввода ФИО
        if not step:
            step = 'fio'
            registration_manager.start_registration(chat_id)
        
        if step == 'fio':
            if not validate_fio(text):
                error_msg = (
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
                    "• Макиавелли Никколо Ди Бернардо Деи"
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
            # Если не нашли активное меню, проверяем статус пользователя
            logger.warning(f"Контент удален, но активное меню не найдено для пользователя {chat_id}")
            from src.bot.keyboards import get_main_keyboard
            from src.core.auth import get_user_role
            
            role = get_user_role(chat_id)
            
            # Если пользователь не зарегистрирован, направляем на регистрацию
            if role == "unregistered":
                from src.bot.messages import format_welcome_message
                
                welcome_message = format_welcome_message(is_new_user=True, chat_id=chat_id)
                
                try:
                    await update.message.reply_text(
                        welcome_message,
                        parse_mode='Markdown'
                    )
                    logger.info(f"Направлен незарегистрированный пользователь {chat_id} на процесс регистрации")
                except Exception as e:
                    logger.error(f"Не удалось отправить приветственное сообщение: {e}")
            else:
                # Для зарегистрированных пользователей создаем главное меню
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