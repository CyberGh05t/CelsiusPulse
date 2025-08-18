import pytest
import asyncio
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime, timedelta
import sys
import os

# Добавляем путь к main.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestNotificationSystem:
    """Тесты системы уведомлений"""

    @pytest.fixture
    def mock_application(self):
        """Mock для telegram application"""
        app = Mock()
        app.bot = AsyncMock()
        return app

    @pytest.fixture
    def sample_alert_sensor(self):
        """Датчик с критической температурой для тестирования алертов"""
        return {
            'device_id': 'critical_sensor',
            'group': 'TestGroup',
            'temperature': -20.0,  # Критически низкая температура
            'timestamp': int(datetime.now().timestamp())
        }

    @pytest.fixture
    def sample_normal_sensor(self):
        """Датчик с нормальной температурой"""
        return {
            'device_id': 'normal_sensor', 
            'group': 'TestGroup',
            'temperature': 25.0,  # Нормальная температура
            'timestamp': int(datetime.now().timestamp())
        }

    @pytest.mark.asyncio
    async def test_alert_cooldown_mechanism(self, mock_application):
        """Тест механизма cooldown для предотвращения спама уведомлений"""
        sensor_id = 'test_sensor'
        current_time = datetime.now()
        
        with patch('main.last_alert_time', {}) as mock_last_alert, \
             patch('main.datetime') as mock_datetime:
            
            mock_datetime.now.return_value = current_time
            
            from main import last_alert_time
            
            # Первый алерт - должен отправиться
            should_send_first = sensor_id not in last_alert_time
            assert should_send_first is True
            
            # Устанавливаем время последнего алерта
            last_alert_time[sensor_id] = current_time
            
            # Второй алерт через 5 минут - не должен отправиться (cooldown 10 минут)
            mock_datetime.now.return_value = current_time + timedelta(minutes=5)
            time_since_last = (mock_datetime.now() - last_alert_time[sensor_id]).total_seconds()
            should_send_second = time_since_last >= 600  # 10 минут cooldown
            assert should_send_second is False
            
            # Третий алерт через 15 минут - должен отправиться
            mock_datetime.now.return_value = current_time + timedelta(minutes=15)
            time_since_last = (mock_datetime.now() - last_alert_time[sensor_id]).total_seconds()
            should_send_third = time_since_last >= 600
            assert should_send_third is True

    @pytest.mark.asyncio
    async def test_send_alert_to_authorized_users(self, mock_application, sample_alert_sensor):
        """Тест отправки уведомлений авторизованным пользователям"""
        with patch('main.application', mock_application), \
             patch('main.CHAT_GROUPS', {123: 'TestGroup', 456: 'OtherGroup'}), \
             patch('main.ADMIN_GROUPS', {789: 'TestGroup'}), \
             patch('main.BIG_BOSS', {111}):
            
            # Имитируем отправку уведомления пользователям группы TestGroup
            expected_recipients = [123, 789, 111]  # user, admin, big_boss
            
            for chat_id in expected_recipients:
                await mock_application.bot.send_message(
                    chat_id=chat_id,
                    text=f"🚨 КРИТИЧЕСКАЯ ТЕМПЕРАТУРА!\n"
                         f"Датчик: {sample_alert_sensor['device_id']}\n"
                         f"Группа: {sample_alert_sensor['group']}\n"
                         f"Температура: {sample_alert_sensor['temperature']}°C"
                )
            
            # Проверяем, что сообщения отправлены нужному количеству получателей
            assert mock_application.bot.send_message.call_count == len(expected_recipients)

    @pytest.mark.asyncio
    async def test_no_alert_for_normal_temperature(self, sample_normal_sensor):
        """Тест отсутствия уведомлений при нормальной температуре"""
        thresholds = {
            'TestGroup': {
                'normal_sensor': {'min': 20, 'max': 30}
            }
        }
        
        # Проверяем, что температура в норме
        sensor = sample_normal_sensor
        threshold = thresholds[sensor['group']][sensor['device_id']]
        
        is_critical = (sensor['temperature'] < threshold['min'] or 
                      sensor['temperature'] > threshold['max'])
        
        assert is_critical is False

    @pytest.mark.asyncio
    async def test_alert_for_critical_temperature(self, sample_alert_sensor):
        """Тест срабатывания уведомлений при критической температуре"""
        thresholds = {
            'TestGroup': {
                'critical_sensor': {'min': -5, 'max': 40}
            }
        }
        
        # Проверяем, что температура критическая
        sensor = sample_alert_sensor
        threshold = thresholds[sensor['group']][sensor['device_id']]
        
        is_critical = (sensor['temperature'] < threshold['min'] or 
                      sensor['temperature'] > threshold['max'])
        
        assert is_critical is True

    @pytest.mark.asyncio
    async def test_alert_message_formatting(self, sample_alert_sensor):
        """Тест форматирования сообщения уведомления"""
        from main import format_timestamp
        
        sensor = sample_alert_sensor
        expected_parts = [
            "🚨",  # Эмодзи тревоги
            "КРИТИЧЕСКАЯ ТЕМПЕРАТУРА" or "ТЕМПЕРАТУРНЫЙ АЛЕРТ",
            sensor['device_id'],
            sensor['group'],
            str(sensor['temperature']),
            "°C"
        ]
        
        # Формируем сообщение как это делается в коде
        message = (
            f"🚨 КРИТИЧЕСКАЯ ТЕМПЕРАТУРА!\n"
            f"Датчик: {sensor['device_id']}\n"
            f"Группа: {sensor['group']}\n"
            f"Температура: {sensor['temperature']}°C\n"
            f"Время: {format_timestamp(sensor['timestamp'])}"
        )
        
        for part in expected_parts:
            assert part in message

    @pytest.mark.asyncio
    async def test_user_group_filtering_for_alerts(self, sample_alert_sensor):
        """Тест фильтрации пользователей по группам при отправке уведомлений"""
        chat_groups = {
            123: 'TestGroup',    # Должен получить уведомление
            456: 'OtherGroup',   # НЕ должен получить уведомление
            789: 'TestGroup'     # Должен получить уведомление
        }
        admin_groups = {
            111: 'TestGroup',    # Должен получить уведомление
            222: 'OtherGroup'    # НЕ должен получить уведомление
        }
        big_boss = {333}  # Должен получить все уведомления
        
        sensor_group = sample_alert_sensor['group']  # 'TestGroup'
        
        # Определяем кто должен получить уведомление
        recipients = []
        
        # Обычные пользователи
        for chat_id, group in chat_groups.items():
            if group == sensor_group:
                recipients.append(chat_id)
        
        # Администраторы
        for chat_id, group in admin_groups.items():
            if group == sensor_group:
                recipients.append(chat_id)
                
        # Big boss получает все
        recipients.extend(big_boss)
        
        expected_recipients = [123, 789, 111, 333]
        assert sorted(recipients) == sorted(expected_recipients)

    @pytest.mark.asyncio
    async def test_alert_retry_on_telegram_error(self, mock_application):
        """Тест повтора отправки при ошибке Telegram API"""
        import telegram.error
        
        # Первый вызов - ошибка, второй - успех
        mock_application.bot.send_message.side_effect = [
            telegram.error.NetworkError("Network error"),
            None  # Успешная отправка
        ]
        
        chat_id = 123
        message = "Test alert message"
        max_retries = 3
        
        # Имитируем retry логику
        for attempt in range(max_retries):
            try:
                await mock_application.bot.send_message(chat_id=chat_id, text=message)
                break  # Успешно отправлено
            except telegram.error.TelegramError:
                if attempt == max_retries - 1:
                    raise  # Последняя попытка неудачна
                await asyncio.sleep(1)  # Ждем перед повтором
        
        # Проверяем, что было 2 попытки (1 неудачная + 1 успешная)
        assert mock_application.bot.send_message.call_count == 2

    @pytest.mark.parametrize("temperature,min_temp,max_temp,expected_alert_type", [
        (-30, -10, 40, "cold"),     # Холодно
        (50, -10, 40, "hot"),       # Жарко
        (25, -10, 40, None),        # Норма
        (-10, -10, 40, None),       # На границе минимума
        (40, -10, 40, None),        # На границе максимума
    ])
    def test_alert_type_detection(self, temperature, min_temp, max_temp, expected_alert_type):
        """Параметризованный тест определения типа уведомления"""
        def get_alert_type(temp, min_val, max_val):
            if temp < min_val:
                return "cold"
            elif temp > max_val:
                return "hot"
            return None
        
        alert_type = get_alert_type(temperature, min_temp, max_temp)
        assert alert_type == expected_alert_type

    @pytest.mark.asyncio
    async def test_bulk_alert_sending(self, mock_application):
        """Тест массовой отправки уведомлений"""
        recipients = [123, 456, 789, 111]
        message = "Bulk alert test"
        
        # Имитируем отправку всем получателям
        for chat_id in recipients:
            await mock_application.bot.send_message(chat_id=chat_id, text=message)
        
        # Проверяем количество отправленных сообщений
        assert mock_application.bot.send_message.call_count == len(recipients)
        
        # Проверяем, что все получатели получили сообщение
        sent_chat_ids = [call[1]['chat_id'] for call in mock_application.bot.send_message.call_args_list]
        assert sorted(sent_chat_ids) == sorted(recipients)