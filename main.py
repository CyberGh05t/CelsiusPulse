"""
CelsiusPulse Bot - Система мониторинга температуры складских помещений
Модульная архитектура с повышенной безопасностью

Главная точка входа приложения
"""
import asyncio
import nest_asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Включаем поддержку вложенных циклов событий
nest_asyncio.apply()

# Импорты модулей приложения
from src.config.settings import TELEGRAM_BOT_TOKEN
from src.config.logging import setup_logging, SecureLogger
from src.core.auth import initialize_groups
from src.core.monitoring import monitor_temperature_loop
from src.bot.handlers.commands import start_command, help_command
from src.bot.handlers.callbacks import button_callback_handler
from src.bot.handlers.admin import handle_text_input, handle_media_input, handle_unknown_command

# Настройка логирования
setup_logging()
logger = SecureLogger(__name__)

# Глобальная переменная для приложения
application = None



async def main():
    """
    Главная функция приложения - как в оригинальной версии
    """
    global application
    try:
        logger.info("🚀 Запуск CelsiusPulse Bot (модульная версия)")
        
        # Проверяем наличие токена
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        
        # Инициализация групп пользователей
        initialize_groups()
        
        # Обновление ролей администраторов
        from src.core.storage import AdminManager
        AdminManager.update_admin_roles()
        
        # Создание приложения Telegram бота - как в оригинале
        logger.info("Инициализация приложения Telegram бота")
        application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Регистрация обработчиков команд
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CallbackQueryHandler(button_callback_handler))
        
        # Обработчик неизвестных команд (исключаем /start и /help)
        application.add_handler(MessageHandler(filters.COMMAND & ~filters.Regex(r'^/(start|help)$'), handle_unknown_command))
        
        # Обработчик текстовых сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
        
        # Обработчики всех типов медиа-файлов
        application.add_handler(MessageHandler(filters.PHOTO, handle_media_input))          # Фото
        application.add_handler(MessageHandler(filters.VIDEO, handle_media_input))          # Видео
        application.add_handler(MessageHandler(filters.AUDIO, handle_media_input))          # Аудио
        application.add_handler(MessageHandler(filters.VOICE, handle_media_input))          # Голосовые сообщения
        application.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_media_input))     # Видеосообщения
        application.add_handler(MessageHandler(filters.Document.ALL, handle_media_input))   # Документы
        application.add_handler(MessageHandler(filters.Sticker.ALL, handle_media_input))    # Стикеры
        application.add_handler(MessageHandler(filters.ANIMATION, handle_media_input))      # GIF-анимации
        application.add_handler(MessageHandler(filters.CONTACT, handle_media_input))        # Контакты
        application.add_handler(MessageHandler(filters.LOCATION, handle_media_input))       # Геолокация
        application.add_handler(MessageHandler(filters.VENUE, handle_media_input))          # Места
        application.add_handler(MessageHandler(filters.POLL, handle_media_input))           # Опросы
        application.add_handler(MessageHandler(filters.Dice.ALL, handle_media_input))       # Кубики/эмодзи
        
        # Дополнительные типы контента для полного покрытия
        application.add_handler(MessageHandler(filters.GAME, handle_media_input))           # Игры
        application.add_handler(MessageHandler(filters.INVOICE, handle_media_input))        # Счета/инвойсы
        application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_media_input))  # Платежи
        application.add_handler(MessageHandler(filters.PASSPORT_DATA, handle_media_input))  # Паспортные данные
        application.add_handler(MessageHandler(filters.STORY, handle_media_input))          # Истории
        application.add_handler(MessageHandler(filters.USER_ATTACHMENT, handle_media_input)) # Вложения
        
        # Специальные типы сообщений
        application.add_handler(MessageHandler(filters.HAS_MEDIA_SPOILER, handle_media_input))      # Медиа со спойлером
        application.add_handler(MessageHandler(filters.HAS_PROTECTED_CONTENT, handle_media_input))  # Защищенный контент
        application.add_handler(MessageHandler(filters.IS_AUTOMATIC_FORWARD, handle_media_input))   # Автопересылка
        application.add_handler(MessageHandler(filters.IS_TOPIC_MESSAGE, handle_media_input))       # Сообщения топиков
        
        # Запуск мониторинга в отдельной задаче - как в оригинале
        asyncio.create_task(monitor_temperature_loop())
        
        logger.info("Все обработчики зарегистрированы")
        logger.info("Бот запущен в режиме polling")
        
        # Запуск бота - как в оригинале
        await application.run_polling()
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())