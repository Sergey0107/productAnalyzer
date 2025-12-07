from typing import Dict, Any

import requests

from config import settings
from llm.llm_provider import LLMProvider
from utils.json_flattener import flatten_json, format_flattened_value
from utils.product_matcher import find_matching_model, merge_series_characteristics


class SpecificationComparator:

    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.client = provider.client
        self.model = provider.model
        self.max_tokens = provider.max_tokens


    def compare_specifications(
        self,
        tz_data: Dict[str, Any],
        passport_data: Dict[str, Any],
        mode: str = "flexible"
    ):

        passport_data = self._process_series_passport(tz_data, passport_data)

        tz_flat = flatten_json(tz_data)
        passport_flat = flatten_json(passport_data)

        print("[DEBUG] Оригинальные данные ТЗ:", tz_data)
        print("[DEBUG] Плоские данные ТЗ:", tz_flat)
        print("[DEBUG] Оригинальные данные паспорта:", passport_data)
        print("[DEBUG] Плоские данные паспорта:", passport_flat)

        prompt = self.create_analysis_prompt(mode)
        full_prompt = f"{prompt}\n\nТЗ:\n{tz_flat}\n\nПаспорт:\n{passport_flat}"

        if settings.LLM_PROVIDER == 'local':  # костыль из за lm studio (или глупого меня)
            url = str(settings.LLM_API_URL).rstrip('/') + '/chat/completions'
            data = {
                'model': self.provider.model,
                'messages': [{
                    "role": "user",
                    "content": full_prompt,
                }]
            }
            response = requests.post(url, json=data)
            return response.json()

        messages = [{
            "role": "user",
            "content": full_prompt
        }]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )

        # Конвертируем в dict
        response_dict = response.to_dict()

        data_response = {
            'response': response_dict,
            'tz_data': tz_flat,
            'passport_data': passport_flat
        }

        return data_response

    def create_analysis_prompt(self, mode: str = "flexible"):
        if mode == "strict":
            return """
    Ты — система для сравнения технических характеристик изделия из двух источников:
    ТЗ (техническое задание) - первый json  и Паспорта изделия - второй json.

    СТРОГИЙ РЕЖИМ: Сравнивай характеристики точно по названиям и значениям.

    Сравни значения по всем критериям из ТЗ.
    Для каждого критерия оцени:
    - соответствует ли фактическое значение ожидаемому,
    - если не соответствует — чем именно,
    - если в паспорте отсутствует значение — status = "missing".

    Верни результат строго в формате JSON БЕЗ каких-либо пояснений, текста, markdown-блоков и т.д.

    Формат ответа:

    {
      "matched": true | false,
      "criteria_success": [ "список критериев, которые полностью соответствуют" ],
      "criteria_error": [ "список критериев, которые не соответствуют или отсутствуют" ],
      "details": {
          "criterion_name": {
              "status": "matched" | "mismatched" | "missing",
              "expected": "значение из ТЗ",
              "actual": "значение из паспорта или null",
              "message": "краткое объяснение"
          }
      }
    }

    Требования:
    - Если хотя бы один критерий несовместим — matched = false.
    - Если значение отсутствует — status = "missing", actual = null.
    - Никакого текста вне JSON.
    """
        else:
            return """
    Ты — система для сравнения технических характеристик изделия из двух источников:
    ТЗ (техническое задание) - первый json  и Паспорта изделия - второй json.

    ГИБКИЙ РЕЖИМ: Интуитивно понимай смысл характеристик и сравнивай их по смыслу, а не по точному названию.

    Примеры эквивалентных характеристик:
    - "Мощность электродвигателя в кВт" ≈ "Потребляемая мощность" ≈ "Мощность" (если единицы совпадают)
    - "Напряжение питания" ≈ "Номинальное напряжение" ≈ "Рабочее напряжение"
    - "Габаритные размеры" ≈ "Размеры" ≈ "Длина x Ширина x Высота"
    - "Масса" ≈ "Вес"

    Игнорируй различия в формулировках, если суть характеристики одинакова.
    Учитывай единицы измерения при сравнении значений.

    Сравни значения по всем критериям из ТЗ.
    Для каждого критерия оцени:
    - соответствует ли фактическое значение ожидаемому по смыслу,
    - если не соответствует — чем именно,
    - если в паспорте отсутствует аналогичная характеристика — status = "missing".

    Верни результат строго в формате JSON БЕЗ каких-либо пояснений, текста, markdown-блоков и т.д.

    Формат ответа:

    {
      "matched": true | false,
      "criteria_success": [ "список критериев, которые полностью соответствуют" ],
      "criteria_error": [ "список критериев, которые не соответствуют или отсутствуют" ],
      "details": {
          "criterion_name": {
              "status": "matched" | "mismatched" | "missing",
              "expected": "значение из ТЗ",
              "actual": "значение из паспорта или null",
              "message": "краткое объяснение"
          }
      }
    }

    Требования:
    - Если хотя бы один критерий несовместим — matched = false.
    - Если значение отсутствует — status = "missing", actual = null.
    - Никакого текста вне JSON.
    """

    def _process_series_passport(
        self,
        tz_data: Dict[str, Any],
        passport_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Обрабатывает паспорт серии изделий.
        Если паспорт содержит серию, находит конкретную модель из ТЗ и
        объединяет общие и специфичные характеристики.

        Args:
            tz_data: Данные из ТЗ
            passport_data: Данные из паспорта

        Returns:
            Обработанные данные паспорта (либо оригинальные, либо для конкретной модели)
        """
        # Проверяем, является ли паспорт серийным
        if not passport_data.get("is_series", False):
            # Обычный паспорт одного изделия - возвращаем как есть
            return passport_data

        print("[DEBUG] Обнаружен паспорт серии изделий")

        # Извлекаем наименование изделия из ТЗ
        requested_product_name = self._extract_product_name_from_tz(tz_data)

        if not requested_product_name:
            print("[DEBUG] Не удалось извлечь наименование из ТЗ, используем общие характеристики серии")
            # Если не нашли наименование - возвращаем общие характеристики серии
            return passport_data.get("common_characteristics", {})

        print(f"[DEBUG] Запрошенное изделие из ТЗ: {requested_product_name}")

        # Получаем список моделей из паспорта
        models = passport_data.get("models", [])

        if not models:
            print("[DEBUG] Список моделей пуст, используем общие характеристики серии")
            return passport_data.get("common_characteristics", {})

        print(f"[DEBUG] Доступные модели в паспорте: {models}")


        matched_model = find_matching_model(requested_product_name, models)

        if not matched_model:
            print(f"[DEBUG] Не найдено соответствие для '{requested_product_name}', используем общие характеристики серии")
            result = passport_data.get("common_characteristics", {})
            result["_warning"] = f"Конкретная модель '{requested_product_name}' не найдена в серии. Используются общие характеристики."
            return result

        print(f"[DEBUG] Найдено соответствие: {matched_model}")


        common_characteristics = passport_data.get("common_characteristics", {})


        model_specific_characteristics = passport_data.get("model_specific_characteristics", {})
        specific_chars = model_specific_characteristics.get(matched_model, {})


        merged_characteristics = merge_series_characteristics(
            common_characteristics,
            specific_chars
        )


        merged_characteristics["_matched_model"] = matched_model
        merged_characteristics["_series_name"] = passport_data.get("series_name", "")

        print(f"[DEBUG] Характеристики объединены для модели: {matched_model}")

        return merged_characteristics

    def _extract_product_name_from_tz(self, tz_data: Dict[str, Any]) -> str:

        if "items" in tz_data and isinstance(tz_data["items"], list) and len(tz_data["items"]) > 0:
            first_item = tz_data["items"][0]
            # Пробуем разные варианты ключей для наименования
            for key in ["Наименование", "наименование", "name", "Name", "product_name"]:
                if key in first_item:
                    return first_item[key]


        for key in ["Наименование", "наименование", "name", "Name", "product_name", "наименование_изделия"]:
            if key in tz_data:
                return tz_data[key]

        return ""


def json_compare_specifications(
    tz_data: Dict[str, Any],
    passport_data: Dict[str, Any],
    mode: str = "flexible"
) -> Dict[str, Any]:

    provider = LLMProvider(settings.LLM_PROVIDER)
    comparator = SpecificationComparator(provider)
    return comparator.compare_specifications(tz_data, passport_data, mode)