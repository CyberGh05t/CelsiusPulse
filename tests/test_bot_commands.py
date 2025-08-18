import pytest
import asyncio
from unittest.mock import patch, Mock, AsyncMock
import sys
import os

# Добавляем путь к main.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBotCommands:
    """Тесты команд бота"""

    @pytest.mark.asyncio
    async def test_start_command_new_user(self, sample_update, mock_context, mock_env):
        """Тест команды /start для нового пользователя"""
        with patch('main.load_admin_info') as mock_load_admin:
            mock_load_admin.return_value = {"groups": []}
            
            from main import start
            await start(sample_update, mock_context)
            
            # Проверяем, что бот отправил сообщение
            mock_context.bot.send_message.assert_called()
            args = mock_context.bot.send_message.call_args[1]
            assert "Добро пожаловать" in args['text'] or "регистрации" in args['text']

    @pytest.mark.asyncio
    async def test_start_command_existing_user(self, sample_update, mock_context, mock_env):
        """Тест команды /start для существующего пользователя"""
        with patch('main.load_admin_info') as mock_load_admin, \
             patch('main.show_interface') as mock_show_interface:
            
            mock_load_admin.return_value = {'fio': 'Test User', 'position': 'Tester', 'groups': []}
            
            from main import start
            await start(sample_update, mock_context)
            
            # Проверяем, что была вызвана функция показа интерфейса
            mock_show_interface.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_interface_regular_user(self, sample_update, mock_context, mock_env):
        """Тест показа интерфейса для обычного пользователя"""
        with patch('main.get_user_role') as mock_get_role, \
             patch('main.CHAT_GROUPS', {123: 'Group1'}):
            
            mock_get_role.return_value = 'user'
            
            from main import show_interface
            await show_interface(sample_update, mock_context, 'user')
            
            # Проверяем, что отправлено сообщение с клавиатурой
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'reply_markup' in args

    @pytest.mark.asyncio
    async def test_show_interface_admin_user(self, sample_update, mock_context, mock_env):
        """Тест показа интерфейса для администратора"""
        with patch('main.get_user_role') as mock_get_role, \
             patch('main.ADMIN_GROUPS', {123: 'Admin1'}):
            
            mock_get_role.return_value = 'admin'
            
            from main import show_interface
            await show_interface(sample_update, mock_context, 'admin')
            
            # Проверяем, что отправлено сообщение с расширенной клавиатурой
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'reply_markup' in args
            # Проверяем наличие админских кнопок
            keyboard = args['reply_markup'].inline_keyboard
            button_texts = [button.text for row in keyboard for button in row]
            assert any('🏢 Все группы' in text for text in button_texts)

    @pytest.mark.asyncio
    async def test_show_interface_big_boss(self, sample_update, mock_context, mock_env):
        """Тест показа интерфейса для big boss"""
        with patch('main.get_user_role') as mock_get_role, \
             patch('main.BIG_BOSS', {123}):
            
            mock_get_role.return_value = 'big_boss'
            
            from main import show_interface
            await show_interface(sample_update, mock_context, 'big_boss')
            
            # Проверяем, что отправлено сообщение с полной клавиатурой
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'reply_markup' in args
            # Проверяем наличие кнопок big boss
            keyboard = args['reply_markup'].inline_keyboard
            button_texts = [button.text for row in keyboard for button in row]
            assert any('👥 Список администраторов' in text for text in button_texts)

    @pytest.mark.asyncio
    async def test_select_group_with_data(self, sample_update, mock_context, mock_env, sample_sensor_data):
        """Тест выбора группы с данными"""
        with patch('main.sensor_data_cache', sample_sensor_data['message']):
            
            from main import select_group
            await select_group(sample_update, mock_context)
            
            # Проверяем, что отправлено сообщение с группами
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'reply_markup' in args
            keyboard = args['reply_markup'].inline_keyboard
            button_texts = [button.text for row in keyboard for button in row]
            # Проверяем наличие групп из тестовых данных
            assert any('Group1' in text for text in button_texts)
            assert any('Group2' in text for text in button_texts)

    @pytest.mark.asyncio
    async def test_select_group_no_data(self, sample_update, mock_context, mock_env):
        """Тест выбора группы без данных"""
        with patch('main.sensor_data_cache', []):
            
            from main import select_group
            await select_group(sample_update, mock_context)
            
            # Проверяем, что отправлено сообщение об отсутствии данных
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert "Данные датчиков недоступны" in args['text']

    @pytest.mark.asyncio
    async def test_admin_all_thresholds(self, sample_update, mock_context, mock_env):
        """Тест просмотра всех пороговых значений администратором"""
        with patch('main.get_user_role') as mock_get_role, \
             patch('main.load_thresholds') as mock_load_thresholds:
            
            mock_get_role.return_value = 'admin'
            mock_load_thresholds.return_value = {
                'Group1': {'sensor_1': {'min': 20, 'max': 30}},
                'Group2': {'sensor_2': {'min': -5, 'max': 5}}
            }
            
            from main import admin_all_thresholds
            await admin_all_thresholds(sample_update, mock_context)
            
            # Проверяем, что отправлено сообщение с пороговыми значениями
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'Group1' in args['text']
            assert 'sensor_1' in args['text']

    @pytest.mark.asyncio  
    async def test_admin_all_thresholds_unauthorized(self, sample_update, mock_context, mock_env):
        """Тест просмотра пороговых значений неавторизованным пользователем"""
        with patch('main.get_user_role') as mock_get_role:
            
            mock_get_role.return_value = 'user'
            
            from main import admin_all_thresholds
            await admin_all_thresholds(sample_update, mock_context)
            
            # Проверяем, что отправлено сообщение об отказе доступа
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert "доступа" in args['text'] or "Недостаточно прав" in args['text']

    @pytest.mark.asyncio
    async def test_list_admins_big_boss(self, sample_update, mock_context, mock_env):
        """Тест просмотра списка администраторов big boss"""
        with patch('main.get_user_role') as mock_get_role, \
             patch('main.ADMIN_GROUPS', {789: 'Admin1', 456: 'Admin2'}), \
             patch('main.load_admin_info') as mock_load_admin:
            
            mock_get_role.return_value = 'big_boss'
            mock_load_admin.side_effect = [
                {'fio': 'Admin User 1', 'position': 'Manager'},
                {'fio': 'Admin User 2', 'position': 'Supervisor'}
            ]
            
            from main import list_admins
            await list_admins(sample_update, mock_context)
            
            # Проверяем, что отправлено сообщение со списком администраторов
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert 'Admin User 1' in args['text']
            assert 'Manager' in args['text']

    @pytest.mark.asyncio
    async def test_list_admins_unauthorized(self, sample_update, mock_context, mock_env):
        """Тест просмотра списка администраторов неавторизованным пользователем"""
        with patch('main.get_user_role') as mock_get_role:
            
            mock_get_role.return_value = 'user'
            
            from main import list_admins
            await list_admins(sample_update, mock_context)
            
            # Проверяем, что отправлено сообщение об отказе доступа
            mock_context.bot.send_message.assert_called_once()
            args = mock_context.bot.send_message.call_args[1]
            assert "доступа" in args['text'] or "Недостаточно прав" in args['text']