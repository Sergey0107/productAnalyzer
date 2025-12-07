from typing import Dict, Any, List


def deduplicate_tz_items(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Объединяет дублирующиеся позиции в ТЗ по наименованию.
    Если одно изделие встречается несколько раз - объединяет их характеристики.
    """
    if not isinstance(data, dict) or 'items' not in data:
        return data

    items = data.get('items', [])
    if not isinstance(items, list):
        return data

    # Словарь для группировки по наименованию
    grouped_items = {}

    for item in items:
        if not isinstance(item, dict):
            continue

        name = item.get('Наименование', '').strip()
        if not name:
            continue

        if name not in grouped_items:
            # Первое вхождение - сохраняем как есть
            grouped_items[name] = item.copy()
        else:
            # Дубликат - объединяем характеристики
            existing = grouped_items[name]

            # Объединяем технические характеристики
            existing_chars = existing.get('Технические характеристики', '').strip()
            new_chars = item.get('Технические характеристики', '').strip()

            if new_chars and new_chars not in existing_chars:
                # Добавляем новые характеристики через пробел
                combined = f"{existing_chars} {new_chars}".strip()
                existing['Технические характеристики'] = combined

            # Количество берем из первого вхождения (уже есть в existing)
            # Единицу измерения тоже берем из первого

    # Преобразуем обратно в список
    result = {
        'items': list(grouped_items.values())
    }

    print(f"[DEBUG] Дедупликация ТЗ: было {len(items)} позиций, стало {len(result['items'])}")

    return result