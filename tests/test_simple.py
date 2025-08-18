import pytest
from unittest.mock import patch, Mock
import sys
import os

# Добавляем путь к main.py  
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSimple:
    """Упрощенные тесты основных функций"""

    def test_get_user_role(self, mock_env):
        """Тест функции get_user_role"""
        with patch('main.CHAT_GROUPS', {123: 'Group1'}), \
             patch('main.ADMIN_GROUPS', {789: 'Admin1'}), \
             patch('main.BIG_BOSS', {111}):
            
            from main import get_user_role
            
            assert get_user_role(123) == 'user'
            assert get_user_role(789) == 'admin' 
            assert get_user_role(111) == 'big_boss'
            assert get_user_role(999) == 'user'

    def test_get_user_group(self, mock_env):
        """Тест функции get_user_group"""
        with patch('main.CHAT_GROUPS', {123: 'Group1'}), \
             patch('main.ADMIN_GROUPS', {789: ['Admin1']}), \
             patch('main.BIG_BOSS', {111}):
            
            from main import get_user_group
            
            assert get_user_group(123) == 'Group1'
            assert get_user_group(789) == 'Admin1'
            assert get_user_group(111) == ''
            assert get_user_group(999) == ''

    def test_format_timestamp(self):
        """Тест форматирования временной метки"""
        from main import format_timestamp
        
        timestamp = 1620000000
        result = format_timestamp(timestamp)
        
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_sensor_message(self):
        """Тест форматирования сообщения датчика"""
        from main import format_sensor_message
        
        sensor = {
            'device_id': 'test_sensor',
            'group': 'TestGroup',
            'temperature': 25.5,
            'timestamp': 1620000000
        }
        
        result = format_sensor_message(sensor)
        
        assert isinstance(result, str)
        assert 'test_sensor' in result
        assert '25.5' in result
        assert 'TestGroup' in result

    @pytest.mark.asyncio
    async def test_fetch_sensor_data_mock(self):
        """Тест получения данных датчиков с mock"""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'status': 'success',
                'message': [{'device_id': 'test', 'temperature': 20}]
            }
            mock_get.return_value = mock_response
            
            from main import fetch_sensor_data
            
            result = await fetch_sensor_data()
            assert result == [{'device_id': 'test', 'temperature': 20}]

    def test_load_thresholds_empty_file(self, temp_files):
        """Тест загрузки пороговых значений из пустого файла"""
        import json
        
        with open(temp_files['thresholds'], 'w') as f:
            json.dump({}, f)
            
        with patch('main.THRESHOLDS_FILE', temp_files['thresholds']):
            from main import load_thresholds
            
            result = load_thresholds()
            assert result == {}

    def test_save_thresholds(self, temp_files):
        """Тест сохранения пороговых значений"""
        import json
        
        test_data = {'Group1': {'sensor1': {'min': 10, 'max': 30}}}
        
        with patch('main.THRESHOLDS_FILE', temp_files['thresholds']):
            from main import save_thresholds
            
            save_thresholds(test_data)
            
            with open(temp_files['thresholds'], 'r') as f:
                saved_data = json.load(f)
            
            assert saved_data == test_data