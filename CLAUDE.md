# Claude Code Instructions for CelsiusPulse Bot

## Project Overview

Telegram бот для мониторинга температуры на складских помещениях с многоуровневым контролем доступа и автоматическими уведомлениями.

## Current Project Structure

```
TempMonitor/
├── main.py                 # Точка входа приложения
├── requirements.txt        # Python зависимости
├── pyproject.toml         # Конфигурация проекта
├── pytest.ini            # Настройки тестирования
├── CLAUDE.md              # Инструкции (этот файл)
├── config/
│   └── docker/
│       └── docker-compose.yml
├── data/                  # Персистентные данные
│   ├── admins.json        # Данные администраторов
│   ├── thresholds.json    # Пороговые значения
│   └── logs/              # Логи приложения
├── docs/                  # Документация
│   ├── CODE_REVIEW.md     # Результаты кодревью
│   ├── CONTRIBUTING.md    # Гайд для разработчиков
│   └── README.md          # Основная документация
├── scripts/               # Служебные скрипты
│   └── unblock_bigboss.py
├── src/                   # Исходный код
│   ├── bot/               # Telegram bot логика
│   │   ├── handlers/      # Обработчики команд/коллбеков
│   │   ├── keyboards.py   # Клавиатуры
│   │   └── messages.py    # Форматирование сообщений
│   ├── config/            # Конфигурация
│   │   ├── logging.py     # Настройки логирования
│   │   └── settings.py    # Настройки приложения
│   ├── core/              # Основная бизнес-логика
│   │   ├── auth.py        # Авторизация и роли
│   │   ├── monitoring.py  # Мониторинг датчиков
│   │   └── storage.py     # Работа с данными
│   └── utils/             # Утилиты
│       ├── security.py    # Безопасность
│       └── validators.py  # Валидация данных
└── tests/                 # Тесты
    ├── conftest.py        # Фикстуры
    └── test_*.py          # Модульные тесты
```

## Key Architecture Points

1. **Модульная структура**: Четкое разделение на bot, core, config, utils
2. **Async архитектура**: asyncio с nest_asyncio для совместимости
3. **Конфигурация**: Все настройки через .env файл
4. **Персистентность**: JSON файлы для пороговых значений и админов
5. **Мониторинг**: Непрерывный цикл проверки температурных датчиков

## Important Guidelines

### DO NOT MODIFY
- User data in production `.env` file
- Existing threshold configurations

### SAFE TO MODIFY
- Documentation files (README, docs/*)
- Docker configurations
- CI/CD workflows
- Test files
- Setup scripts

## Common Tasks

### 1. Добавление новых функций
При добавлении функций следуй структуре:
```python
# Для bot логики: src/bot/handlers/
# Для core логики: src/core/
# Для утилит: src/utils/
# Импорты в main.py только при необходимости
```

### 2. Improving Error Handling
- Add try-catch blocks around external API calls
- Implement retry logic with exponential backoff
- Log all errors with full context

### 3. Performance Optimization
- Cache frequently accessed data
- Batch database operations
- Use connection pooling for external services

### 4. Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test
pytest tests/test_bot.py::test_start_command
```

### 5. Миграция на базу данных
При переходе с JSON на БД:
1. Создать скрипт миграции в `scripts/migrate_to_db.py`
2. Сохранить обратную совместимость
3. Тщательно тестировать на копии продакшн данных

## Code Style

- Follow PEP 8
- Use Black formatter (line length: 88)
- Type hints where possible
- Docstrings for all functions/classes

## Environment Setup

1. **Development**:
```bash
cp .env.example .env.development
# Edit with test tokens
```

2. **Testing**:
```bash
cp .env.example .env.test
# Use mock data sources
```

3. **Production**:
```bash
# Use secrets management
# Never commit production .env
```

## Common Issues & Solutions

### Issue: Bot doesn't respond
- Check token validity
- Verify network connectivity
- Review logs for errors

### Issue: Alerts not sending
- Check threshold configuration
- Verify alert cooldown settings
- Ensure monitoring loop is running

### Issue: Memory leak
- Check for unclosed connections
- Review async task cleanup
- Monitor with memory profiler

## Deployment Checklist

### Основные проверки
- [ ] All tests passing
- [ ] Environment variables configured
- [ ] Logs directory exists with write permissions
- [ ] Backup strategy in place
- [ ] Monitoring endpoints configured
- [ ] Rate limiting enabled
- [ ] SSL certificates valid (for webhooks)

### Критические проверки безопасности
- [ ] **Bandit security scan** - нет критических уязвимостей
- [ ] **Safety dependency check** - все зависимости безопасны  
- [ ] **Secrets detection** - нет секретов в коде
- [ ] **File permissions** - .env файлы имеют права 600
- [ ] **Input validation** - все пользовательские данные валидируются
- [ ] **Error handling** - ошибки не раскрывают системную информацию
- [ ] **Logging security** - чувствительные данные замаскированы
- [ ] **Rate limiting** - защита от спама и DDoS настроена
- [ ] **Admin access** - только авторизованные администраторы
- [ ] **Token rotation** - все токены и ключи обновлены

## API Integration

Current data source: Google Apps Script
Expected response format:
```json
{
  "status": "success",
  "message": [
    {
      "device_id": "sensor_1_3",
      "group": "KRR",
      "temperature": 23.5,
      "timestamp": 1234567890
    }
  ]
}
```

## Security Considerations

**КРИТИЧНО: Весь код должен быть максимально защищен от всевозможных атак и перехватов!**

### Основные принципы безопасности

1. **Конфиденциальность данных**:
   - Никогда не выводить в логи: Bot tokens, API keys, chat IDs, пароли
   - Шифровать чувствительные данные в файлах конфигурации
   - Использовать переменные окружения для секретов
   - Регулярно ротировать токены и ключи

2. **Защита от входных данных**:
   - **Всегда валидировать** все пользовательские данные
   - Санитизировать входные строки (защита от SQL injection, XSS)
   - Ограничивать длину сообщений и параметров
   - Проверять типы данных перед обработкой

3. **Защита от атак**:
   - **Rate limiting**: максимум запросов в минуту на пользователя
   - **DDoS защита**: блокировка подозрительного трафика
   - **Brute force защита**: временная блокировка после неудачных попыток
   - **Command injection защита**: валидация всех системных команд

4. **Сетевая безопасность**:
   - Использовать только HTTPS для всех внешних запросов
   - Проверять SSL сертификаты при запросах к API
   - Настроить firewall для ограничения исходящих подключений
   - Использовать VPN для критических подключений

5. **Мониторинг и аудит**:
   - Логировать все подозрительные действия
   - Мониторить неудачные попытки авторизации
   - Отслеживать необычные паттерны использования
   - Настроить алерты на подозрительную активность

6. **Защита файловой системы**:
   - Ограничить права доступа к файлам (chmod 600 для .env)
   - Регулярные бекапы с проверкой целостности
   - Защита от path traversal атак
   - Валидация имен файлов при загрузке

### Обязательные проверки безопасности

```python
# Пример безопасной валидации
def validate_user_input(text: str) -> bool:
    # Проверка длины
    if len(text) > MAX_MESSAGE_LENGTH:
        return False
    
    # Проверка на вредоносные символы
    dangerous_chars = ['<', '>', '&', '"', "'", ';', '|', '`']
    if any(char in text for char in dangerous_chars):
        return False
    
    # Проверка на SQL injection паттерны
    sql_patterns = ['union', 'select', 'drop', 'insert', 'update', 'delete']
    text_lower = text.lower()
    if any(pattern in text_lower for pattern in sql_patterns):
        return False
    
    return True

# Пример безопасного логирования
def secure_log(message: str, sensitive_data: dict = None):
    # Маскировать чувствительные данные
    if sensitive_data:
        for key in ['token', 'password', 'key', 'secret']:
            if key in sensitive_data:
                sensitive_data[key] = '***MASKED***'
    
    logger.info(f"Secure operation: {message}", extra=sensitive_data)
```

### Проверки перед релизом

- [ ] Проверить отсутствие хардкодированных секретов в коде
- [ ] Запустить сканер безопасности (bandit, safety)
- [ ] Проверить настройки rate limiting
- [ ] Убедиться в корректной валидации всех входных данных
- [ ] Проверить логи на предмет утечки чувствительной информации
- [ ] Обновить все зависимости до последних безопасных версий

### Инциденты безопасности

При обнаружении подозрительной активности:
1. Немедленно заблокировать подозрительных пользователей
2. Сменить все токены и ключи доступа
3. Проанализировать логи за последние 24 часа
4. Уведомить администраторов о инциденте
5. Документировать инцидент для анализа

## Monitoring & Observability

### Key Metrics to Track
- Response time for commands
- Alert delivery success rate
- API call failures
- Memory/CPU usage
- Active users count

### Logging Strategy
- INFO: Normal operations
- WARNING: Recoverable issues
- ERROR: Failures requiring attention
- CRITICAL: System-breaking issues

## Useful Commands for Development

```bash
# Format code
black . --line-length 88

# Lint code
flake8 . --max-line-length 88

# Type checking
mypy main.py

# Security scans (ОБЯЗАТЕЛЬНО перед релизом!)
bandit -r . --format json -o security_report.json
safety check --json --output safety_report.json
pip-audit --format=json --output=audit_report.json

# Check for secrets in code
detect-secrets scan --all-files --baseline .secrets.baseline

# Dependency security check
python -m pip_audit --desc --format=json

# Update dependencies securely
pip-compile requirements.in --upgrade
safety check -r requirements.txt

# Generate documentation
sphinx-build -b html docs/ docs/_build/

# Check file permissions (production)
find . -name "*.env*" -exec ls -la {} \;
```

## Contact for Questions

For architectural decisions or major changes, consult with the team lead before implementation.

## Особенности текущей реализации

1. **Вложенные event loops**: Используется nest_asyncio для совместимости с telegram-bot
2. **Глобальные переменные**: Для кеша и состояния приложения (нужен рефакторинг в классы)
3. **Файловое хранение**: JSON файлы для персистентности (подходит для малого/среднего масштаба)
4. **Модульная архитектура**: Разделение на bot/core/config/utils пакеты
5. **Безопасность**: Комплексная валидация, rate limiting, санитизация входных данных

## Future Improvements to Consider

1. Implement proper state management (Redis/Database)
2. Add health check endpoints
3. Implement metrics collection (Prometheus)
4. Add internationalization support
5. Create admin web dashboard
6. Implement data archiving strategy
7. Add predictive alerts using ML

Remember: Maintain backward compatibility and test thoroughly before deploying any changes! Все комментарии, инструкции и документации пиши на русском языке. Разговаривай с пользователем по русски.

## Code Review Reference

📋 **Current code review:** `docs/CODE_REVIEW.md` (Overall: 8/10)

**Critical issues to keep in mind:**
1. Global variables for cache (need CacheManager class)
2. No retry logic for API calls
3. Unencrypted config files
4. Code duplication in handlers

**Working principles:**
- ✅ Держать в уме весь файл CLAUDE.md при каждом обращении
- ✅ Применять фиксы только после подтверждения ИЛИ автоматом если разрешено для сессии
- ✅ Предлагать улучшения только в финальном резюме
- ✅ Экономить токены, не читать файлы без необходимости
- ✅ Консоль и все сообщения на русском языке
- ❌ Не заёбывать напоминаниями о известных проблемах