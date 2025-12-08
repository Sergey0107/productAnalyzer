from typing import Any, Dict


def flatten_json(data: Dict[str, Any], parent_key: str = '', separator: str = ' - ') -> Dict[str, Any]:
    """
    Преобразует вложенный JSON в плоскую структуру.

    Пример:
    {
        "Габаритные размеры": {
            "Длина, не более мм": "500",
            "Ширина, не более мм": "300"
        },
        "Требования к комплектации": [
            "Агрегат центробежный на опорах – 1шт",
            "Запасные уплотнения всех соединение по 3 единицы (молочных муфт)"
        ]
    }

    Превращается в:
    {
        "Габаритные размеры - Длина, не более мм": "500",
        "Габаритные размеры - Ширина, не более мм": "300",
        "Требования к комплектации": "Агрегат центробежный на опорах – 1шт; Запасные уплотнения всех соединение по 3 единицы (молочных муфт)"
    }

    Args:
        data: Исходный JSON (словарь)
        parent_key: Родительский ключ для рекурсии
        separator: Разделитель между уровнями вложенности

    Returns:
        Плоский словарь
    """
    items = []

    for key, value in data.items():
        new_key = f"{parent_key}{separator}{key}" if parent_key else key

        if isinstance(value, dict):
            items.extend(flatten_json(value, new_key, separator=separator).items())
        elif isinstance(value, list):
            if all(isinstance(item, (str, int, float, bool)) for item in value):
                items.append((new_key, '; '.join(str(item) for item in value)))
            else:
                if key == "items" and len(value) == 1 and isinstance(value[0], dict):
                    items.extend(flatten_json(value[0], parent_key, separator=separator).items())
                else:
                    for idx, item in enumerate(value):
                        if isinstance(item, dict):
                            items.extend(flatten_json(item, f"{new_key}[{idx}]", separator=separator).items())
                        else:
                            items.append((f"{new_key}[{idx}]", str(item)))
        else:
            items.append((new_key, value))

    return dict(items)


def format_flattened_value(value: Any) -> str:
    """
    Форматирует значение для отображения в UI.

    Args:
        value: Значение любого типа

    Returns:
        Отформатированная строка
    """
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        return value
    elif isinstance(value, (list, dict)):
        # На случай если что-то не распаковалось
        import json
        return json.dumps(value, ensure_ascii=False)
    else:
        return str(value)