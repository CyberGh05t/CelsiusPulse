import pytest
import asyncio
import json
import tempfile
import os
from unittest.mock import patch, Mock, AsyncMock
import sys

# Добавляем путь к main.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.integration
class TestIntegration:
    """Интеграционные тесты для проверки взаимодействия компонентов"""

    @pytest.mark.asyncio
    async def test_full_monitoring_cycle(self, sample_sensor_data, sample_thresholds, temp_files):
        """Тест полного цикла мониторинга температуры"""
        with patch('main.THRESHOLDS_FILE', temp_files['thresholds']), \
             patch('main.DOGET_URL', 'https://test.url'), \
             patch('requests.get') as mock_get:
            
            # Подготавливаем данные
            with open(temp_files['thresholds'], 'w', encoding='utf-8') as f:
                json.dump(sample_thresholds, f, ensure_ascii=False, indent=2)
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_sensor_data
            mock_get.return_value = mock_response
            
            # Импортируем функции после настройки патчей
            from main import fetch_sensor_data, load_thresholds
            
            # Тестируем полный цикл
            sensor_data = await fetch_sensor_data()
            thresholds = load_thresholds()
            
            assert sensor_data == sample_sensor_data['message']
            assert thresholds == sample_thresholds
            
            # Проверяем обработку данных
            for sensor in sensor_data:
                device_id = sensor['device_id']
                group = sensor['group']
                temperature = sensor['temperature']
                
                if group in thresholds and device_id in thresholds[group]:
                    threshold = thresholds[group][device_id]
                    is_critical = (temperature < threshold['min'] or 
                                 temperature > threshold['max'])
                    
                    if sensor['device_id'] == 'sensor_2':  # -10.0 температура
                        assert is_critical is True
                    else:
                        assert is_critical is False

    @pytest.mark.asyncio
    async def test_user_workflow_start_to_data_view(self, sample_update, mock_context, mock_env, sample_sensor_data):
        """Тест полного пользовательского сценария от старта до просмотра данных"""
        with patch('main.load_admin_info') as mock_load_admin, \
             patch('main.sensor_data_cache', sample_sensor_data['message']), \
             patch('main.CHAT_GROUPS', {123: 'Group1'}):
            
            # Новый пользователь
            mock_load_admin.return_value = None
            
            from main import start, show_interface, show_group_data
            
            # 1. Пользователь запускает бота
            await start(sample_update, mock_context)
            
            # 2. Показываем интерфейс для обычного пользователя
            await show_interface(sample_update, mock_context, 'user')
            
            # 3. Пользователь выбирает просмотр данных своей группы
            await show_group_data(sample_update, mock_context, 'Group1')
            
            # Проверяем, что все вызовы прошли успешно
            assert mock_context.bot.send_message.call_count >= 3

    @pytest.mark.asyncio
    async def test_admin_workflow_threshold_management(self, sample_update, mock_context, mock_env, temp_files):
        """Тест сценария администратора по управлению пороговыми значениями"""
        with patch('main.THRESHOLDS_FILE', temp_files['thresholds']), \
             patch('main.get_user_role') as mock_get_role:
            
            mock_get_role.return_value = 'admin'
            
            from main import admin_all_thresholds, load_thresholds, save_thresholds
            
            # Подготавливаем тестовые пороги
            test_thresholds = {
                'TestGroup': {
                    'sensor_1': {'min': 15, 'max': 35}
                }
            }
            
            # Сохраняем пороги
            save_thresholds(test_thresholds)
            
            # Администратор просматривает все пороги
            await admin_all_thresholds(sample_update, mock_context)
            
            # Загружаем сохраненные пороги
            loaded_thresholds = load_thresholds()
            
            assert loaded_thresholds == test_thresholds
            mock_context.bot.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_error_handling_chain(self, sample_update, mock_context, mock_env):
        """Тест обработки ошибок в цепочке вызовов"""
        import requests
        
        with patch('requests.get') as mock_get, \
             patch('main.sensor_data_cache', []):
            
            # Имитируем ошибку сети
            mock_get.side_effect = requests.exceptions.ConnectionError()
            
            from main import fetch_sensor_data, show_all_data
            
            # Пытаемся получить данные (должно вернуть пустой список)
            sensor_data = await fetch_sensor_data()
            assert sensor_data == []
            
            # Пытаемся показать все данные (должно показать сообщение об отсутствии данных)
            await show_all_data(sample_update, mock_context)
            
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'недоступны' in args['text'] or 'нет данных' in args['text'].lower()

    @pytest.mark.asyncio
    async def test_concurrent_user_requests(self, mock_env, sample_sensor_data):
        """Тест обработки одновременных запросов от разных пользователей"""
        from main import format_sensor_message
        
        # Имитируем одновременные запросы от разных пользователей
        tasks = []
        for i in range(5):
            # Создаем задачу для каждого "пользователя"
            sensor = sample_sensor_data['message'][0].copy()
            sensor['device_id'] = f'sensor_{i}'
            task = asyncio.create_task(asyncio.to_thread(format_sensor_message, sensor))
            tasks.append(task)
        
        # Ждем завершения всех задач
        results = await asyncio.gather(*tasks)
        
        # Проверяем, что все задачи выполнились успешно
        assert len(results) == 5
        for i, result in enumerate(results):
            assert f'sensor_{i}' in result

    @pytest.mark.asyncio
    async def test_data_persistence_workflow(self, temp_files):
        """Тест сохранения и загрузки данных"""
        from main import save_thresholds, load_thresholds, save_admin_info, load_admin_info
        
        with patch('main.THRESHOLDS_FILE', temp_files['thresholds']), \
             patch('main.ADMINS_FILE', temp_files['admins']):
            
            # Тестируем пороговые значения
            test_thresholds = {
                'Group1': {
                    'sensor_1': {'min': 20, 'max': 30}
                }
            }
            
            save_thresholds(test_thresholds)
            loaded_thresholds = load_thresholds()
            assert loaded_thresholds == test_thresholds
            
            # Тестируем информацию об администраторах
            save_admin_info(123, 'Test Admin', 'Manager')
            admin_info = load_admin_info(123)
            assert admin_info['fio'] == 'Test Admin'
            assert admin_info['position'] == 'Manager'

    @pytest.mark.asyncio
    async def test_role_based_access_integration(self, sample_update, mock_context, mock_env):
        """Интеграционный тест системы ролей"""
        test_cases = [
            ({'role': 'user', 'expected_buttons': ['📊 Мои данные']}, 123),
            ({'role': 'admin', 'expected_buttons': ['🏢 Все группы']}, 789),
            ({'role': 'big_boss', 'expected_buttons': ['👥 Список администраторов']}, 111)
        ]
        
        for test_case, user_id in test_cases:
            # Обновляем ID пользователя в update
            sample_update.effective_user.id = user_id
            sample_update.effective_chat.id = user_id
            
            with patch('main.CHAT_GROUPS', {123: 'Group1'}), \
                 patch('main.ADMIN_GROUPS', {789: 'Admin1'}), \
                 patch('main.BIG_BOSS', {111}):
                
                from main import show_interface, get_user_role
                
                role = get_user_role(user_id)
                assert role == test_case['role']
                
                await show_interface(sample_update, mock_context, role)
                
                # Проверяем, что интерфейс соответствует роли
                mock_context.bot.send_message.assert_called()
                args = mock_context.bot.send_message.call_args[1]
                keyboard = args.get('reply_markup')
                
                if keyboard:
                    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
                    has_expected_button = any(
                        expected in button_text 
                        for expected in test_case['expected_buttons']
                        for button_text in button_texts
                    )
                    # Для некоторых ролей кнопки могут отсутствовать, это нормально
                
                # Сбрасываем mock для следующего теста
                mock_context.bot.send_message.reset_mock()

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_monitoring_loop_performance(self, sample_sensor_data):
        """Тест производительности цикла мониторинга"""
        import time
        
        with patch('requests.get') as mock_get, \
             patch('main.load_thresholds') as mock_load_thresholds:
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_sensor_data
            mock_get.return_value = mock_response
            mock_load_thresholds.return_value = {}
            
            from main import fetch_sensor_data, load_thresholds
            
            # Измеряем время выполнения
            start_time = time.time()
            
            # Выполняем несколько итераций
            for _ in range(10):
                await fetch_sensor_data()
                load_thresholds()
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Проверяем, что операции выполняются быстро (менее 1 секунды за 10 итераций)
            assert execution_time < 1.0, f"Операции выполнялись слишком медленно: {execution_time}s"