from typing import Dict, Any

import requests

from config import settings
from modules.llm_provider import LLMProvider


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
        print(tz_data)
        print(passport_data)
        prompt = self.create_analysis_prompt(mode)
        full_prompt = f"{prompt}\n\nТЗ:\n{tz_data}\n\nПаспорт:\n{passport_data}"
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
            'tz_data': tz_data,
            'passport_data': passport_data
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


def json_compare_specifications(
    tz_data: Dict[str, Any],
    passport_data: Dict[str, Any],
    mode: str = "flexible"
) -> Dict[str, Any]:

    provider = LLMProvider(settings.LLM_PROVIDER)
    comparator = SpecificationComparator(provider)
    return comparator.compare_specifications(tz_data, passport_data, mode)