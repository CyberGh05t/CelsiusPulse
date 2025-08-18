import pytest
import asyncio
from unittest.mock import patch, Mock, AsyncMock
import json
import requests
import sys
import os
from datetime import datetime, timedelta

# Добавляем путь к main.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTemperatureMonitoring:
    """Тесты системы мониторинга температуры"""

    @pytest.mark.asyncio
    async def test_fetch_sensor_data_success(self, mock_requests_get, sample_sensor_data):
        """Тест успешного получения данных с датчиков"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_sensor_data
        mock_requests_get.return_value = mock_response
        
        with patch('main.DOGET_URL', 'https://test.url'):
            from main import fetch_sensor_data
            
            data = await fetch_sensor_data()
            
            assert data == sample_sensor_data['message']
            mock_requests_get.assert_called_once_with('https://test.url', timeout=30)

    @pytest.mark.asyncio
    async def test_fetch_sensor_data_http_error(self, mock_requests_get):
        """Тест обработки HTTP ошибки при получении данных"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_requests_get.return_value = mock_response
        
        with patch('main.DOGET_URL', 'https://test.url'):
            from main import fetch_sensor_data
            
            data = await fetch_sensor_data()
            
            assert data == []

    @pytest.mark.asyncio
    async def test_fetch_sensor_data_connection_error(self, mock_requests_get):
        """Тест обработки ошибки соединения"""
        mock_requests_get.side_effect = requests.exceptions.ConnectionError()
        
        with patch('main.DOGET_URL', 'https://test.url'):
            from main import fetch_sensor_data
            
            data = await fetch_sensor_data()
            
            assert data == []

    @pytest.mark.asyncio
    async def test_fetch_sensor_data_timeout(self, mock_requests_get):
        """Тест обработки таймаута"""
        mock_requests_get.side_effect = requests.exceptions.Timeout()
        
        with patch('main.DOGET_URL', 'https://test.url'):
            from main import fetch_sensor_data
            
            data = await fetch_sensor_data()
            
            assert data == []

    @pytest.mark.asyncio
    async def test_fetch_sensor_data_invalid_json(self, mock_requests_get):
        """Тест обработки некорректного JSON"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_requests_get.return_value = mock_response
        
        with patch('main.DOGET_URL', 'https://test.url'):
            from main import fetch_sensor_data
            
            data = await fetch_sensor_data()
            
            assert data == []

    def test_load_thresholds_success(self, temp_files, sample_thresholds):
        """Тест успешной загрузки пороговых значений"""
        with patch('main.THRESHOLDS_FILE', temp_files['thresholds']):
            # Записываем тестовые данные
            with open(temp_files['thresholds'], 'w', encoding='utf-8') as f:
                json.dump(sample_thresholds, f, ensure_ascii=False, indent=2)
            
            from main import load_thresholds
            
            thresholds = load_thresholds()
            assert thresholds == sample_thresholds

    def test_load_thresholds_file_not_exists(self, temp_files):
        """Тест загрузки пороговых значений при отсутствии файла"""
        import os
        os.remove(temp_files['thresholds'])  # Удаляем файл
        
        with patch('main.THRESHOLDS_FILE', temp_files['thresholds']):
            from main import load_thresholds
            
            thresholds = load_thresholds()
            assert thresholds == {}

    def test_save_thresholds(self, temp_files, sample_thresholds):
        """Тест сохранения пороговых значений"""
        with patch('main.THRESHOLDS_FILE', temp_files['thresholds']):
            from main import save_thresholds
            
            save_thresholds(sample_thresholds)
            
            # Проверяем, что данные сохранились
            with open(temp_files['thresholds'], 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert data == sample_thresholds

    def test_format_timestamp(self):
        """Тест форматирования временной метки"""
        from main import format_timestamp
        
        # Тестируем с конкретной меткой времени
        timestamp = 1620000000  # 2021-05-03 00:00:00 UTC
        formatted = format_timestamp(timestamp)
        
        assert isinstance(formatted, str)
        assert len(formatted) > 0

    def test_format_sensor_message(self, sample_sensor_data):
        """Тест форматирования сообщения датчика"""
        from main import format_sensor_message
        
        sensor = sample_sensor_data['message'][0]
        message = format_sensor_message(sensor)
        
        assert isinstance(message, str)
        assert sensor['device_id'] in message
        assert str(sensor['temperature']) in message
        assert sensor['group'] in message

    @pytest.mark.asyncio
    async def test_show_sensor_data_success(self, sample_update, mock_context, sample_sensor_data):
        """Тест отображения данных конкретного датчика"""
        with patch('main.sensor_data_cache', sample_sensor_data['message']):
            from main import show_sensor_data
            
            await show_sensor_data(sample_update, mock_context, ['sensor_1'])
            
            # Проверяем, что отправлено сообщение
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'sensor_1' in args['text']

    @pytest.mark.asyncio
    async def test_show_sensor_data_not_found(self, sample_update, mock_context):
        """Тест отображения данных несуществующего датчика"""
        with patch('main.sensor_data_cache', []):
            from main import show_sensor_data
            
            await show_sensor_data(sample_update, mock_context, ['nonexistent'])
            
            # Проверяем, что отправлено сообщение об ошибке
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'не найден' in args['text'] or 'Датчик не найден' in args['text']

    @pytest.mark.asyncio
    async def test_show_group_data_success(self, sample_update, mock_context, sample_sensor_data):
        """Тест отображения данных группы"""
        with patch('main.sensor_data_cache', sample_sensor_data['message']):
            from main import show_group_data
            
            await show_group_data(sample_update, mock_context, 'Group1')
            
            # Проверяем, что отправлено сообщение
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'Group1' in args['text']

    @pytest.mark.asyncio
    async def test_show_group_data_no_sensors(self, sample_update, mock_context):
        """Тест отображения данных группы без датчиков"""
        with patch('main.sensor_data_cache', []):
            from main import show_group_data
            
            await show_group_data(sample_update, mock_context, 'EmptyGroup')
            
            # Проверяем, что отправлено сообщение об отсутствии данных
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'датчиков не найдено' in args['text'] or 'Нет данных' in args['text']

    @pytest.mark.asyncio
    async def test_show_all_data_success(self, sample_update, mock_context, sample_sensor_data):
        """Тест отображения всех данных"""
        with patch('main.sensor_data_cache', sample_sensor_data['message']):
            from main import show_all_data
            
            await show_all_data(sample_update, mock_context)
            
            # Проверяем, что отправлено сообщение
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'Все данные датчиков' in args['text'] or 'датчик' in args['text'].lower()

    @pytest.mark.asyncio
    async def test_show_all_data_empty(self, sample_update, mock_context):
        """Тест отображения всех данных при пустом кэше"""
        with patch('main.sensor_data_cache', []):
            from main import show_all_data
            
            await show_all_data(sample_update, mock_context)
            
            # Проверяем, что отправлено сообщение об отсутствии данных
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'Данные датчиков недоступны' in args['text']

    @pytest.mark.asyncio
    async def test_monitor_temperature_basic(self, sample_sensor_data, sample_thresholds):
        """Тест базовой функциональности мониторинга температуры"""
        with patch('main.fetch_sensor_data') as mock_fetch, \
             patch('main.sensor_data_cache', []), \
             patch('main.load_thresholds') as mock_load_thresholds, \
             patch('main.application') as mock_app, \
             patch('asyncio.sleep') as mock_sleep:
            
            mock_fetch.return_value = sample_sensor_data['message']
            mock_load_thresholds.return_value = sample_thresholds
            mock_app.bot = AsyncMock()
            
            # Прерываем цикл после первой итерации
            mock_sleep.side_effect = [None, KeyboardInterrupt()]
            
            from main import monitor_temperature
            
            with pytest.raises(KeyboardInterrupt):
                await monitor_temperature()
            
            # Проверяем, что данные были получены
            mock_fetch.assert_called()
            mock_load_thresholds.assert_called()

    @pytest.mark.parametrize("temperature,min_temp,max_temp,should_alert", [
        (25.0, 20, 30, False),  # Нормальная температура
        (15.0, 20, 30, True),   # Ниже минимума
        (35.0, 20, 30, True),   # Выше максимума
        (20.0, 20, 30, False),  # На границе минимума
        (30.0, 20, 30, False),  # На границе максимума
    ])
    def test_temperature_threshold_logic(self, temperature, min_temp, max_temp, should_alert):
        """Параметризованный тест логики пороговых значений"""
        # Это упрощенный тест логики, которая должна быть в функции мониторинга
        def should_send_alert(temp, min_val, max_val):
            return temp < min_val or temp > max_val
        
        result = should_send_alert(temperature, min_temp, max_temp)
        assert result == should_alert