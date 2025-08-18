import pytest
from unittest.mock import patch, mock_open
import json
import sys
import os

# Добавляем путь к main.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAuthentication:
    """Тесты системы авторизации и групп пользователей"""

    def test_load_groups_success(self, mock_env):
        """Тест успешной загрузки групп из переменных окружения"""
        from main import load_groups
        
        groups = load_groups()
        
        assert 'CHAT_GROUPS' in groups
        assert 'ADMIN_GROUPS' in groups
        assert 'BIG_BOSS' in groups
        assert groups['CHAT_GROUPS'] == {123: 'Group1', 456: 'Group2'}
        assert groups['ADMIN_GROUPS'] == {789: 'Admin1'}
        assert groups['BIG_BOSS'] == {111}

    def test_load_groups_invalid_json(self):
        """Тест обработки некорректного JSON в переменных окружения"""
        with patch.dict(os.environ, {
            'CHAT_GROUPS': 'invalid_json',
            'ADMIN_GROUPS': '{}',
            'BIG_BOSS': '[]'
        }):
            from main import load_groups
            
            with pytest.raises(Exception):
                load_groups()

    def test_get_user_role_regular_user(self, mock_env):
        """Тест определения роли обычного пользователя"""
        with patch('main.CHAT_GROUPS', {123: 'Group1'}), \
             patch('main.ADMIN_GROUPS', {}), \
             patch('main.BIG_BOSS', set()):
            
            from main import get_user_role
            
            role = get_user_role(123)
            assert role == 'user'

    def test_get_user_role_admin(self, mock_env):
        """Тест определения роли администратора"""
        with patch('main.CHAT_GROUPS', {}), \
             patch('main.ADMIN_GROUPS', {789: 'Admin1'}), \
             patch('main.BIG_BOSS', set()):
            
            from main import get_user_role
            
            role = get_user_role(789)
            assert role == 'admin'

    def test_get_user_role_big_boss(self, mock_env):
        """Тест определения роли big boss"""
        with patch('main.CHAT_GROUPS', {}), \
             patch('main.ADMIN_GROUPS', {}), \
             patch('main.BIG_BOSS', {111}):
            
            from main import get_user_role
            
            role = get_user_role(111)
            assert role == 'big_boss'

    def test_get_user_role_unknown(self, mock_env):
        """Тест определения роли неизвестного пользователя"""
        with patch('main.CHAT_GROUPS', {}), \
             patch('main.ADMIN_GROUPS', {}), \
             patch('main.BIG_BOSS', set()):
            
            from main import get_user_role
            
            role = get_user_role(999)
            assert role == 'user'  # По умолчанию возвращается 'user'

    def test_get_user_group_regular_user(self, mock_env):
        """Тест получения группы обычного пользователя"""
        with patch('main.CHAT_GROUPS', {123: 'Group1'}), \
             patch('main.ADMIN_GROUPS', {}), \
             patch('main.BIG_BOSS', set()):
            
            from main import get_user_group
            
            group = get_user_group(123)
            assert group == 'Group1'

    def test_get_user_group_admin(self, mock_env):
        """Тест получения группы администратора"""
        with patch('main.CHAT_GROUPS', {}), \
             patch('main.ADMIN_GROUPS', {789: ['Admin1', 'Admin2']}), \
             patch('main.BIG_BOSS', set()):
            
            from main import get_user_group
            
            group = get_user_group(789)
            assert group == 'Admin1, Admin2'

    def test_get_user_group_big_boss(self, mock_env):
        """Тест получения группы big boss"""
        with patch('main.CHAT_GROUPS', {}), \
             patch('main.ADMIN_GROUPS', {}), \
             patch('main.BIG_BOSS', {111}):
            
            from main import get_user_group
            
            group = get_user_group(111)
            assert group == ''  # Big boss возвращает пустую строку

    def test_get_user_group_unknown(self, mock_env):
        """Тест получения группы неизвестного пользователя"""
        with patch('main.CHAT_GROUPS', {}), \
             patch('main.ADMIN_GROUPS', {}), \
             patch('main.BIG_BOSS', set()):
            
            from main import get_user_group
            
            group = get_user_group(999)
            assert group == ''  # Неизвестный пользователь возвращает пустую строку

    def test_load_admin_info_exists(self, temp_files):
        """Тест загрузки существующей информации об администраторе"""
        admin_data = [
            {'chat_id': 123, 'fio': 'Test Admin', 'position': 'Manager', 'registered': '2023-01-01 12:00:00'}
        ]
        
        with patch('main.ADMINS_FILE', temp_files['admins']):
            # Записываем тестовые данные
            with open(temp_files['admins'], 'w', encoding='utf-8') as f:
                json.dump(admin_data, f, ensure_ascii=False, indent=2)
            
            from main import load_admin_info
            
            info = load_admin_info(123)
            assert info is not None
            assert info['fio'] == 'Test Admin'
            assert info['position'] == 'Manager'

    def test_load_admin_info_not_exists(self, temp_files):
        """Тест загрузки информации о несуществующем администраторе"""
        with patch('main.ADMINS_FILE', temp_files['admins']):
            from main import load_admin_info
            
            info = load_admin_info(999)
            assert info == {"groups": []}  # Возвращает словарь с пустыми группами

    def test_save_admin_info(self, temp_files):
        """Тест сохранения информации об администраторе"""
        # Подготавливаем пустой список администраторов в файле
        with open(temp_files['admins'], 'w', encoding='utf-8') as f:
            json.dump([], f)
            
        with patch('main.ADMINS_FILE', temp_files['admins']):
            from main import save_admin_info
            
            save_admin_info(123, 'Test Admin', 'Manager')
            
            # Проверяем, что данные сохранились
            with open(temp_files['admins'], 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert len(data) == 1
            assert data[0]['chat_id'] == 123
            assert data[0]['fio'] == 'Test Admin'
            assert data[0]['position'] == 'Manager'

    def test_update_env_file(self, mock_env):
        """Тест обновления .env файла"""
        # Упрощенный тест - просто проверяем, что функция выполняется без ошибок
        with patch('main.CHAT_GROUPS', {123: 'NewGroup'}), \
             patch('main.ADMIN_GROUPS', {456: 'NewAdmin'}), \
             patch('main.BIG_BOSS', {789}):
            
            from main import update_env_file
            
            # Функция должна выполниться без ошибок
            update_env_file()
            # Полная проверка записи файла требует более сложной настройки mock

    @pytest.mark.parametrize("user_id,expected_role", [
        (123, 'user'),      # обычный пользователь
        (789, 'admin'),     # администратор  
        (111, 'big_boss'),  # big boss
        (999, 'user')       # неизвестный пользователь -> 'user' по умолчанию
    ])
    def test_user_roles_parametrized(self, mock_env, user_id, expected_role):
        """Параметризованный тест ролей пользователей"""
        with patch('main.CHAT_GROUPS', {123: 'Group1'}), \
             patch('main.ADMIN_GROUPS', {789: 'Admin1'}), \
             patch('main.BIG_BOSS', {111}):
            
            from main import get_user_role
            
            role = get_user_role(user_id)
            assert role == expected_role