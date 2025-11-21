from pathlib import Path
from typing import Dict, Any, Union

import requests
from pypdf import PdfReader

from config import settings
from modules.base_analyzer import BaseAnalyzer
from modules.llm_provider import LLMProvider


class PassportAnalyzer(BaseAnalyzer):

    def analyze_passport_file(self, file_path: Union[str, Path]):
        prompt = self.create_analysis_prompt()
        return self.analyze(file_path, prompt)

    def create_analysis_prompt(self):
        return 'Верни все обнаруженные в тексте или файле технические характеристики изделия строго в формате JSON: ключ — имя характеристики, значение — её числовое или текстовое значение; если характеристика содержит единицы измерения, сохрани их; не изменяй названия характеристик; не придумывай данные; если значение отсутствует, укажи null; в ответе должен быть только JSON и ничего больше.'

    def analyze(self, file_path, prompt):
        try:

            if settings.LLM_PROVIDER == 'local':
                pdf_text = ""

                if file_path:
                    reader = PdfReader(file_path)
                    for page in reader.pages:
                        pdf_text += page.extract_text() + "\n"

                full_prompt = f"{prompt}\n\n---\nТекст PDF:\n{pdf_text}"

                url = str(settings.LLM_API_URL).rstrip('/') + '/chat/completions'

                data = {
                    "model": self.provider.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": full_prompt
                        }
                    ]
                }

                response = requests.post(url, json=data)
                return response.json()

            else:

                messages = [{
                    "role": "user",
                    "content": prompt
                }]

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages
                )
                return response.choices[0].message.content

        except Exception as e:
            raise ValueError(f"Ошибка OpenAI API: {str(e)}")


def analyze_passport_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    llm_provider = LLMProvider(settings.LLM_PROVIDER)
    analyzer = PassportAnalyzer(llm_provider)
    return analyzer.analyze_passport_file(file_path)
