"""
Модуль мониторинга температуры
Получение данных с датчиков и проверка пороговых значений
"""
import asyncio
import requests
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from ..config.settings import DOGET_URL, MONITORING_INTERVAL, ALERT_COOLDOWN
from ..config.logging import SecureLogger
from ..utils.validators import validate_temperature, validate_device_id, validate_group_name
from ..utils.security import validate_request_security
from .storage import ThresholdManager

logger = SecureLogger(__name__)

# Глобальные переменные для кеширования данных
sensor_data_cache: List[Dict[str, Any]] = []
last_successful_cache: List[Dict[str, Any]] = []  # Последний успешный кеш
last_successful_cache_time: Optional[datetime] = None
last_alert_time: Dict[str, datetime] = {}
threshold_cache: Dict[str, Any] = {}
threshold_cache_time: Optional[datetime] = None
THRESHOLD_CACHE_TTL = 300  # 5 минут кеш

# Максимальное время жизни последнего успешного кеша (1 час)
LAST_CACHE_MAX_AGE = 3600  # секунд


def fetch_sensor_data() -> List[Dict[str, Any]]:
    """
    Получает данные с датчиков от внешнего API
    
    Returns:
        Список данных датчиков
    """
    logger.debug("Запрос данных сенсоров...")
    start_time = datetime.now()
    
    try:
        # Валидация URL
        if not DOGET_URL:
            logger.error("DOGET_URL не настроен")
            return []
        
        # Выполняем запрос к API
        response = requests.get(DOGET_URL, timeout=10)
        response.raise_for_status()
        
        # Парсим JSON ответ
        data = response.json()
        
        # Валидация структуры ответа
        if not isinstance(data, dict) or "message" not in data:
            logger.error("Неверная структура ответа API")
            return []
        
        if data.get("status") != "success":
            logger.warning(f"API вернул статус: {data.get('status')}")
            return []
        
        sensors = data.get("message", [])
        if not isinstance(sensors, list):
            logger.error("Поле 'message' должно содержать список")
            return []
        
        # Валидация данных датчиков с сохранением невалидных
        all_sensors = []
        for sensor in sensors:
            if validate_sensor_data(sensor):
                sensor['validation_status'] = 'valid'
                all_sensors.append(sensor)
            else:
                # Помечаем как невалидные, но включаем в результат
                sensor['validation_status'] = 'invalid'
                sensor['validation_errors'] = get_validation_errors(sensor)
                all_sensors.append(sensor)
                logger.warning(f"Невалидные данные датчика (включены в результат): {sensor}")
        
        execution_time = datetime.now() - start_time
        valid_count = sum(1 for s in all_sensors if s.get('validation_status') == 'valid')
        invalid_count = len(all_sensors) - valid_count
        logger.info(f"Данные сенсоров обновлены. Получено {len(all_sensors)} записей "
                   f"(валидных: {valid_count}, невалидных: {invalid_count}). "
                   f"Время выполнения: {execution_time}")
        
        # Обновляем глобальный кеш
        global sensor_data_cache, last_successful_cache, last_successful_cache_time
        sensor_data_cache = all_sensors
        
        # Сохраняем последний успешный кеш, если есть валидные данные
        if any(s.get('validation_status') == 'valid' for s in all_sensors):
            last_successful_cache = all_sensors.copy()
            last_successful_cache_time = datetime.now()
            logger.debug("Обновлен последний успешный кеш датчиков")
        
        return all_sensors
    
    except requests.exceptions.ConnectionError:
        logger.error("Ошибка сети при получении данных")
        return []
    except requests.exceptions.Timeout:
        logger.error("Таймаут при получении данных")
        return []
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP ошибка: {e}")
        return []
    except ValueError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении данных: {e}")
        traceback.print_exc()
        return []


def get_validation_errors(sensor: Dict[str, Any]) -> List[str]:
    """
    Возвращает список ошибок валидации для датчика
    
    Args:
        sensor: Словарь с данными датчика
        
    Returns:
        Список описаний ошибок валидации
    """
    errors = []
    required_fields = ["device_id", "group", "temperature", "timestamp"]
    
    # Проверяем наличие обязательных полей
    for field in required_fields:
        if field not in sensor:
            errors.append(f"Отсутствует поле '{field}'")
    
    # Валидируем каждое поле если оно присутствует
    if "device_id" in sensor and not validate_device_id(str(sensor["device_id"])):
        errors.append("Некорректный ID датчика")
    
    if "group" in sensor and not validate_group_name(str(sensor["group"])):
        errors.append("Некорректное имя группы")
    
    if "temperature" in sensor and not validate_temperature(sensor["temperature"]):
        errors.append("Некорректное значение температуры")
    
    # Валидируем timestamp
    if "timestamp" in sensor:
        try:
            timestamp = int(sensor["timestamp"])
            # API возвращает MSK timestamp, корректируем для сравнения с местным UTC временем
            corrected_timestamp = timestamp - 10800  # MSK -> UTC
            now = datetime.now().timestamp()
            if abs(now - corrected_timestamp) > 3600:  # 1 час
                errors.append("Устаревший timestamp (старше 1 часа)")
        except (ValueError, TypeError):
            errors.append("Некорректный формат timestamp")
    
    return errors


def validate_sensor_data(sensor: Dict[str, Any]) -> bool:
    """
    Валидирует данные одного датчика
    
    Args:
        sensor: Словарь с данными датчика
        
    Returns:
        True если данные валидны
    """
    required_fields = ["device_id", "group", "temperature", "timestamp"]
    
    # Проверяем наличие обязательных полей
    for field in required_fields:
        if field not in sensor:
            return False
    
    # Валидируем каждое поле
    if not validate_device_id(str(sensor["device_id"])):
        return False
    
    if not validate_group_name(str(sensor["group"])):
        return False
    
    if not validate_temperature(sensor["temperature"]):
        return False
    
    # Валидируем timestamp
    try:
        timestamp = int(sensor["timestamp"])
        # API возвращает MSK timestamp, корректируем для сравнения с местным UTC временем
        corrected_timestamp = timestamp - 10800  # MSK -> UTC
        # Проверяем, что timestamp не слишком старый и не из будущего
        now = datetime.now().timestamp()
        # Проверяем данные не старше 1 часа
        if abs(now - corrected_timestamp) > 3600:  # 1 час
            logger.warning(f"Old timestamp: {timestamp} (device: {sensor.get('device_id', 'unknown')})")
            return False
    except (ValueError, TypeError):
        return False
    
    return True


def get_cached_thresholds() -> Dict[str, Any]:
    """
    Получает пороговые значения с кешированием
    
    Returns:
        Кешированные пороговые значения
    """
    global threshold_cache, threshold_cache_time
    
    now = datetime.now()
    
    # Проверяем, нужно ли обновить кеш
    if (threshold_cache_time is None or 
        (now - threshold_cache_time).total_seconds() > THRESHOLD_CACHE_TTL):
        
        threshold_cache = ThresholdManager.load_thresholds()
        threshold_cache_time = now
        logger.debug("Threshold cache updated")
    
    return threshold_cache


def check_temperature_threshold(sensor: Dict[str, Any]) -> Optional[str]:
    """
    Проверяет, нарушены ли пороговые значения для датчика
    
    Args:
        sensor: Данные датчика
        
    Returns:
        Сообщение об ошибке или None если все в порядке
    """
    device_id = sensor["device_id"]
    group = sensor["group"]
    temperature = float(sensor["temperature"])
    
    # Получаем пороговые значения из кеша
    thresholds = get_cached_thresholds()
    
    if group not in thresholds or device_id not in thresholds[group]:
        # Нет настроенных порогов для этого датчика
        return None
    
    threshold = thresholds[group][device_id]
    min_temp = threshold.get("min")
    max_temp = threshold.get("max")
    
    if min_temp is not None and temperature < min_temp:
        return f"🥶 НИЗКАЯ ТЕМПЕРАТУРА: {temperature}°C (мин: {min_temp}°C)"
    
    if max_temp is not None and temperature > max_temp:
        return f"🔥 ВЫСОКАЯ ТЕМПЕРАТУРА: {temperature}°C (макс: {max_temp}°C)"
    
    return None


def should_send_alert(device_id: str) -> bool:
    """
    Проверяет, нужно ли отправлять alert для датчика (cooldown механизм)
    
    Args:
        device_id: ID датчика
        
    Returns:
        True если alert нужно отправить
    """
    global last_alert_time
    
    now = datetime.now()
    
    if device_id not in last_alert_time:
        last_alert_time[device_id] = now
        return True
    
    time_since_last = (now - last_alert_time[device_id]).total_seconds()
    
    if time_since_last >= ALERT_COOLDOWN:
        last_alert_time[device_id] = now
        return True
    
    return False


def get_sensors_by_group(group_name: str) -> List[Dict[str, Any]]:
    """
    Возвращает датчики определенной группы
    
    Args:
        group_name: Название группы
        
    Returns:
        Список датчиков группы
    """
    if not validate_group_name(group_name):
        return []
    
    sensors = [
        sensor for sensor in sensor_data_cache 
        if sensor.get("group") == group_name
    ]
    
    # Сортируем датчики по device_id для стабильного порядка отображения
    return sorted(sensors, key=lambda x: x.get("device_id", ""))


def get_sensor_by_id(device_id: str) -> Optional[Dict[str, Any]]:
    """
    Возвращает данные конкретного датчика
    
    Args:
        device_id: ID датчика
        
    Returns:
        Данные датчика или None
    """
    if not validate_device_id(device_id):
        return None
    
    for sensor in sensor_data_cache:
        if sensor.get("device_id") == device_id:
            return sensor
    
    return None


def get_all_groups() -> List[str]:
    """
    Возвращает список всех доступных групп из кеша (БЕЗ фильтрации по ролям)
    
    Returns:
        Список названий групп или пустой список если данные недоступны
    """
    groups = set()
    
    # Пытаемся получить группы из текущего кеша
    for sensor in sensor_data_cache:
        group = sensor.get("group")
        if group and validate_group_name(group):
            groups.add(group)
    
    # Если текущий кеш пуст, используем последний успешный кеш (НО только если он не старше 1 часа)
    if not groups and last_successful_cache and last_successful_cache_time:
        age_seconds = (datetime.now() - last_successful_cache_time).total_seconds()
        
        if age_seconds <= LAST_CACHE_MAX_AGE:  # Не старше 1 часа
            logger.info("Текущий кеш пуст, используем последний успешный кеш")
            for sensor in last_successful_cache:
                group = sensor.get("group")
                if group and validate_group_name(group):
                    groups.add(group)
            
            age_minutes = age_seconds // 60
            logger.info(f"Используется кеш возрастом {age_minutes:.0f} минут")
        else:
            age_minutes = age_seconds // 60
            logger.warning(f"Последний успешный кеш слишком старый ({age_minutes:.0f} минут), не используется")
    
    result = sorted(list(groups))
    
    if not result:
        logger.warning("Нет доступных групп - все кеши пусты или устарели")
    else:
        logger.debug(f"get_all_groups возвращает {len(result)} групп: {result}")
    
    return result


def format_timestamp(unix_timestamp: int) -> str:
    """
    Форматирует unix timestamp в читаемый вид
    
    Args:
        unix_timestamp: Unix timestamp (приходит в MSK от Google Apps Script)
        
    Returns:
        Отформатированная дата и время в локальном часовом поясе
    """
    try:
        # API возвращает timestamp в MSK, но отображаем в местном времени (UTC), вычитаем 3 часа
        corrected_timestamp = unix_timestamp - 10800  # MSK -> UTC для отображения
        local_dt = datetime.fromtimestamp(corrected_timestamp)
        return local_dt.strftime("%d.%m.%Y %H:%M:%S")
    except (ValueError, OSError):
        return "Неизвестно"


def get_monitoring_statistics() -> Dict[str, Any]:
    """
    Возвращает статистику мониторинга (системная функция - все данные)
    
    Returns:
        Словарь со статистикой
    """
    total_sensors = len(sensor_data_cache)
    groups = get_all_groups()
    
    # Подсчет валидных и невалидных датчиков
    valid_sensors = sum(1 for s in sensor_data_cache if s.get('validation_status') == 'valid')
    invalid_sensors = sum(1 for s in sensor_data_cache if s.get('validation_status') == 'invalid')
    
    # Подсчет критических датчиков (только среди валидных)
    critical_sensors = 0
    for sensor in sensor_data_cache:
        if sensor.get('validation_status') == 'valid' and check_temperature_threshold(sensor):
            critical_sensors += 1
    
    return {
        "total_sensors": total_sensors,
        "valid_sensors": valid_sensors,
        "invalid_sensors": invalid_sensors,
        "total_groups": len(groups),
        "critical_sensors": critical_sensors,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cache_size": len(sensor_data_cache)
    }


def get_user_statistics(chat_id: int) -> Dict[str, Any]:
    """
    Возвращает статистику мониторинга с учетом прав доступа пользователя
    
    Args:
        chat_id: ID чата пользователя
        
    Returns:
        Словарь со статистикой (только по доступным группам)
    """
    from .auth import get_user_role, get_user_accessible_groups
    
    # Определяем роль пользователя
    role = get_user_role(chat_id)
    
    # Big Boss видит всю статистику системы
    if role == "big_boss":
        logger.debug(f"BigBoss {chat_id}: возвращаем полную статистику системы")
        return get_monitoring_statistics()
    
    # Для администраторов фильтруем данные по их группам
    elif role == "admin":
        user_groups = get_user_accessible_groups(chat_id)
        logger.debug(f"Админ {chat_id}: фильтруем статистику по группам {user_groups}")
        
        # Фильтруем данные из кеша только по группам администратора
        filtered_data = [
            sensor for sensor in sensor_data_cache 
            if sensor.get('group') in user_groups
        ]
        
        # Подсчитываем статистику только по отфильтрованным данным
        total_sensors = len(filtered_data)
        valid_sensors = sum(1 for s in filtered_data if s.get('validation_status') == 'valid')
        invalid_sensors = sum(1 for s in filtered_data if s.get('validation_status') == 'invalid')
        
        # Разделяем датчики по категориям для анализа
        valid_sensors_list = [s for s in filtered_data if s.get('validation_status') == 'valid']
        invalid_sensors_list = [s for s in filtered_data if s.get('validation_status') == 'invalid']
        
        # Находим критические датчики среди валидных
        critical_sensors_list = []
        for sensor in valid_sensors_list:
            if check_temperature_threshold(sensor):
                critical_sensors_list.append(sensor)
        
        critical_sensors = len(critical_sensors_list)
        
        # Анализируем проблемы для расширенной статистики
        validation_errors_analysis = analyze_validation_errors(invalid_sensors_list)
        critical_issues_analysis = analyze_critical_issues(critical_sensors_list)
        groups_breakdown = analyze_groups_breakdown(filtered_data, user_groups)
        
        return {
            "total_sensors": total_sensors,
            "valid_sensors": valid_sensors,
            "invalid_sensors": invalid_sensors,
            "total_groups": len(user_groups),
            "critical_sensors": critical_sensors,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cache_size": total_sensors,
            # Дополнительные данные для расширенной статистики
            "validation_errors_analysis": validation_errors_analysis,
            "critical_issues_analysis": critical_issues_analysis,
            "groups_breakdown": groups_breakdown,
            "problem_sensors": {
                "invalid": invalid_sensors_list,
                "critical": critical_sensors_list
            }
        }
    
    # Незарегистрированные пользователи не видят статистику
    else:
        logger.warning(f"Незарегистрированный пользователь {chat_id} пытается получить статистику")
        return {
            "total_sensors": 0,
            "valid_sensors": 0,
            "invalid_sensors": 0,
            "total_groups": 0,
            "critical_sensors": 0,
            "last_update": "Недоступно",
            "cache_size": 0
        }


def analyze_validation_errors(invalid_sensors: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Анализирует и группирует ошибки валидации
    
    Args:
        invalid_sensors: Список невалидных датчиков
        
    Returns:
        Словарь с группированными ошибками
    """
    error_counts = {}
    
    for sensor in invalid_sensors:
        errors = sensor.get('validation_errors', [])
        for error in errors:
            # Группируем схожие ошибки
            if "температур" in error.lower():
                key = "Некорректная температура"
            elif "timestamp" in error.lower() and "старше 1 дня" in error.lower():
                key = "Старые данные"
            elif "timestamp" in error.lower():
                key = "Неверный формат времени"
            elif "отсутствует поле" in error.lower():
                key = "Отсутствуют данные"
            else:
                key = "Прочие ошибки"
            
            error_counts[key] = error_counts.get(key, 0) + 1
    
    return error_counts


def analyze_critical_issues(critical_sensors: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Анализирует критические нарушения температуры
    
    Args:
        critical_sensors: Список датчиков с критическими нарушениями
        
    Returns:
        Словарь с типами критических проблем
    """
    critical_counts = {"Перегрев": 0, "Переохлаждение": 0}
    
    for sensor in critical_sensors:
        device_id = sensor.get("device_id", "")
        group = sensor.get("group", "")
        temperature = sensor.get("temperature")
        
        if temperature is None:
            continue
            
        try:
            temp_value = float(temperature)
            threshold_issue = check_temperature_threshold(sensor)
            
            if threshold_issue:
                # Получаем пороги для анализа
                thresholds = get_cached_thresholds()
                if group in thresholds and device_id in thresholds[group]:
                    threshold = thresholds[group][device_id]
                    min_temp = threshold.get("min")
                    max_temp = threshold.get("max")
                    
                    if max_temp is not None and temp_value > max_temp:
                        critical_counts["Перегрев"] += 1
                    elif min_temp is not None and temp_value < min_temp:
                        critical_counts["Переохлаждение"] += 1
        except (ValueError, TypeError):
            continue
    
    # Удаляем нулевые значения
    return {k: v for k, v in critical_counts.items() if v > 0}


def get_sensor_problem_emoji_and_description(sensor: Dict[str, Any], is_critical: bool = False) -> tuple[str, str]:
    """
    Возвращает подходящий эмодзи и краткое описание для проблемы датчика
    
    Args:
        sensor: Данные датчика
        is_critical: True если это критическая проблема температуры
        
    Returns:
        Кортеж (эмодзи, описание)
    """
    if is_critical:
        # Определяем тип критической проблемы
        device_id = sensor.get("device_id", "")
        group = sensor.get("group", "")
        temperature = sensor.get("temperature")
        
        try:
            temp_value = float(temperature)
            thresholds = get_cached_thresholds()
            
            if group in thresholds and device_id in thresholds[group]:
                threshold = thresholds[group][device_id]
                min_temp = threshold.get("min")
                max_temp = threshold.get("max")
                
                if max_temp is not None and temp_value > max_temp:
                    return "🥵", f"{temperature}°C (перегрев)"
                elif min_temp is not None and temp_value < min_temp:
                    return "🥶", f"{temperature}°C (переохлаждение)"
        except (ValueError, TypeError):
            pass
        
        # Если не удалось определить тип - общий критический эмодзи
        return "🔥", f"{temperature}°C (критично)"
    
    else:
        # Анализируем ошибки валидации
        errors = sensor.get('validation_errors', [])
        if not errors:
            return "❌", "неизвестная ошибка"
        
        main_error = errors[0].lower()
        
        # Группируем по типам ошибок с соответствующими эмодзи
        if 'температур' in main_error:
            return "❓", "неверная t°"
        elif 'timestamp' in main_error and 'старше 1 дня' in main_error:
            return "🕒", "старые данные"
        elif 'timestamp' in main_error and 'старше 7 дней' in main_error:
            return "🕒", "очень старые данные"
        elif 'timestamp' in main_error:
            return "📡", "неверный формат времени"
        elif 'отсутствует поле' in main_error:
            if 'temperature' in main_error:
                return "📤", "нет данных t°"
            elif 'timestamp' in main_error:
                return "📤", "нет времени"
            elif 'device_id' in main_error:
                return "📤", "нет ID"
            elif 'group' in main_error:
                return "📤", "нет группы"
            else:
                return "📤", "нет данных"
        elif 'некорректный id датчика' in main_error:
            return "🔧", "некорректный ID"
        elif 'некорректное имя группы' in main_error:
            return "🏷️", "некорректная группа"
        else:
            return "❌", "прочие ошибки"


def analyze_groups_breakdown(filtered_data: List[Dict[str, Any]], user_groups: List[str]) -> Dict[str, Dict[str, int]]:
    """
    Анализирует разбивку датчиков по группам
    
    Args:
        filtered_data: Отфильтрованные данные датчиков
        user_groups: Список групп пользователя
        
    Returns:
        Словарь с разбивкой по группам
    """
    groups_stats = {}
    
    for group in user_groups:
        group_sensors = [s for s in filtered_data if s.get('group') == group]
        valid_count = sum(1 for s in group_sensors if s.get('validation_status') == 'valid')
        invalid_count = sum(1 for s in group_sensors if s.get('validation_status') == 'invalid')
        
        # Подсчитываем критические среди валидных
        critical_count = 0
        for sensor in group_sensors:
            if sensor.get('validation_status') == 'valid' and check_temperature_threshold(sensor):
                critical_count += 1
        
        groups_stats[group] = {
            'total': len(group_sensors),
            'valid': valid_count,
            'critical': critical_count,
            'invalid': invalid_count
        }
    
    return groups_stats


async def monitor_temperature_loop():
    """
    Основной цикл мониторинга температуры
    Проверяет данные и отправляет уведомления при превышении порогов
    """
    logger.info("Запуск службы мониторинга температуры")
    
    while True:
        try:
            # Получаем свежие данные в отдельном потоке чтобы не блокировать event loop
            loop = asyncio.get_event_loop()
            sensors = await loop.run_in_executor(None, fetch_sensor_data)
            
            if not sensors:
                logger.warning("Не получены данные сенсоров")
                await asyncio.sleep(MONITORING_INTERVAL)
                continue
            
            # Проверяем пороговые значения
            critical_sensors = []
            for sensor in sensors:
                alert_message = check_temperature_threshold(sensor)
                if alert_message and should_send_alert(sensor["device_id"]):
                    critical_sensors.append({
                        "sensor": sensor,
                        "alert_message": alert_message
                    })
            
            if critical_sensors:
                logger.warning(f"Обнаружено {len(critical_sensors)} критических датчиков")
                # Здесь будет отправка уведомлений (будет реализовано в bot модуле)
            
            logger.debug(f"Цикл мониторинга, сенсоров: {len(sensors)}")
            
        except Exception as e:
            logger.error(f"Ошибка в цикле мониторинга: {e}")
            traceback.print_exc()
        
        await asyncio.sleep(MONITORING_INTERVAL)