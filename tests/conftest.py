import pytest
import os
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from telegram import Update, User, Chat, Message
from telegram.ext import ContextTypes
import tempfile


@pytest.fixture
def mock_env():
    """Mock переменных окружения для тестов"""
    with patch.dict(os.environ, {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'DOGET_URL': 'https://test.url',
        'CHAT_GROUPS': '{"123": "Group1", "456": "Group2"}',
        'ADMIN_GROUPS': '{"789": "Admin1"}',
        'BIG_BOSS': '[111]'
    }):
        yield


@pytest.fixture
def sample_user():
    """Создает тестового пользователя"""
    return User(
        id=123,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser"
    )


@pytest.fixture
def sample_chat():
    """Создает тестовый чат"""
    from unittest.mock import Mock
    chat = Mock(spec=Chat)
    chat.id = 123
    chat.type = Chat.PRIVATE
    chat.first_name = "Test"
    chat.last_name = "User"
    chat.username = "testuser"
    return chat


@pytest.fixture
def sample_message(sample_user, sample_chat):
    """Создает тестовое сообщение"""
    from unittest.mock import Mock
    message = Mock(spec=Message)
    message.message_id = 1
    message.date = None
    message.chat = sample_chat
    message.from_user = sample_user
    message.text = "/start"
    message.reply_text = AsyncMock()
    return message


@pytest.fixture
def sample_update(sample_message):
    """Создает тестовый Update"""
    from unittest.mock import Mock
    update = Mock(spec=Update)
    update.update_id = 1
    update.message = sample_message
    update.effective_user = sample_message.from_user
    update.effective_chat = sample_message.chat
    return update


@pytest.fixture
def mock_context():
    """Создает mock контекста"""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock()
    context.user_data = {}
    context.chat_data = {}
    return context


@pytest.fixture
def sample_sensor_data():
    """Возвращает тестовые данные датчиков"""
    return {
        "status": "success",
        "message": [
            {
                "device_id": "sensor_1",
                "group": "Group1",
                "temperature": 25.5,
                "timestamp": 1620000000
            },
            {
                "device_id": "sensor_2",
                "group": "Group2", 
                "temperature": -10.0,
                "timestamp": 1620000000
            }
        ]
    }


@pytest.fixture
def sample_thresholds():
    """Возвращает тестовые пороговые значения"""
    return {
        "Group1": {
            "sensor_1": {"min": 20, "max": 30}
        },
        "Group2": {
            "sensor_2": {"min": -5, "max": 5}
        }
    }


@pytest.fixture
def temp_files():
    """Создает временные файлы для тестов"""
    with tempfile.TemporaryDirectory() as temp_dir:
        thresholds_file = os.path.join(temp_dir, "thresholds.json")
        admins_file = os.path.join(temp_dir, "admins.json")
        
        # Создаем тестовые файлы
        with open(thresholds_file, 'w') as f:
            json.dump({}, f)
            
        with open(admins_file, 'w') as f:
            json.dump({}, f)
            
        yield {
            'thresholds': thresholds_file,
            'admins': admins_file,
            'dir': temp_dir
        }


@pytest.fixture
def mock_requests_get():
    """Mock для requests.get"""
    with patch('requests.get') as mock:
        yield mock


@pytest.fixture
def event_loop():
    """Создает новый event loop для каждого теста"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()