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
from src.bot.handlers.admin import handle_text_input

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
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
        
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