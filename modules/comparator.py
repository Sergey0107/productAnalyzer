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
        passport_data: Dict[str, Any]
    ):
        prompt = self.create_analysis_prompt()
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

        # Унифицируем формат возврата для совместимости с local провайдером
        return {
            'choices': [{
                'message': {
                    'content': response.choices[0].message.content
                }
            }]
        }

    def create_analysis_prompt(self):
        return """
    Ты — система для сравнения технических характеристик изделия из двух источников: 
    ТЗ (техническое задание) - первый json  и Паспорта изделия - второй json.

    Сравни значения по всем критериям. 
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


def json_compare_specifications(
    tz_data: Dict[str, Any],
    passport_data: Dict[str, Any],
) -> Dict[str, Any]:

    provider = LLMProvider(settings.LLM_PROVIDER)
    comparator = SpecificationComparator(provider)
    return comparator.compare_specifications(tz_data, passport_data)