"""
Утилита для сопоставления изделия из ТЗ с конкретной моделью из серии в паспорте.
"""
from typing import Optional, Dict, Any
from difflib import SequenceMatcher


def find_matching_model(requested_name: str, models: list[str]) -> Optional[str]:
    """
    Находит наиболее подходящую модель из списка по запрошенному наименованию.

    Args:
        requested_name: Наименование изделия из ТЗ
        models: Список моделей из паспорта

    Returns:
        Наиболее подходящая модель или None, если не найдено
    """
    if not models or not requested_name:
        return None

    requested_name_normalized = normalize_product_name(requested_name)

    best_match = None
    best_score = 0.0

    for model in models:
        model_normalized = normalize_product_name(model)

        # Проверяем точное совпадение
        if requested_name_normalized == model_normalized:
            return model

        # Проверяем частичное совпадение (модель содержится в названии или наоборот)
        if model_normalized in requested_name_normalized or requested_name_normalized in model_normalized:
            score = max(len(model_normalized), len(requested_name_normalized)) / \
                   (len(model_normalized) + len(requested_name_normalized))
            if score > best_score:
                best_score = score
                best_match = model
            continue

        # Вычисляем similarity score
        similarity = SequenceMatcher(None, requested_name_normalized, model_normalized).ratio()

        if similarity > best_score:
            best_score = similarity
            best_match = model

    # Возвращаем результат только если схожесть выше порога
    if best_score >= 0.5:  # порог схожести 50%
        return best_match

    return None


def normalize_product_name(name: str) -> str:
    """
    Нормализует наименование изделия для сравнения.

    Args:
        name: Исходное наименование

    Returns:
        Нормализованное наименование (lowercase, без лишних пробелов)
    """
    if not name:
        return ""

    # Приводим к нижнему регистру
    normalized = name.lower()

    # Убираем множественные пробелы
    normalized = " ".join(normalized.split())

    return normalized


def merge_series_characteristics(
    common_characteristics: Dict[str, Any],
    model_specific: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Объединяет общие характеристики серии с характеристиками конкретной модели.

    Args:
        common_characteristics: Общие характеристики серии
        model_specific: Характеристики конкретной модели

    Returns:
        Объединенный словарь характеристик (model_specific имеет приоритет)
    """
    result = common_characteristics.copy()
    result.update(model_specific)
    return result