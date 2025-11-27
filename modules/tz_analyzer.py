import json
import requests
from typing import Dict, Any, Union, List
from pathlib import Path
from docx import Document
from openai import models
from pyexpat.errors import messages

from config import settings
from modules.base_analyzer import BaseAnalyzer
from modules.llm_provider import LLMProvider


class TzAnalyzer(BaseAnalyzer):

    def analize_tz_file(self, file_path):
        tz_data = self.parse_tz_file(file_path)
        prompt = self.create_analysis_prompt()
        return self.analyze(tz_data, prompt)

    def parse_tz_file(self, file_path: Union[str, Path]) -> list[list[list[Any]]]:
        doc = Document(file_path)
        tz_data = self.search_table(doc)
        return tz_data

    def search_table(self, doc: Document):
        tables_data = []

        for table in doc.tables:
            if len(table.rows) < 2:
                continue

            table_rows = []

            for row in table.rows:
                row_cells = []
                for cell in row.cells:
                    text = " ".join(cell.text.split())
                    row_cells.append(text)
                table_rows.append(row_cells)

            tables_data.append(table_rows)

        return tables_data

    def create_analysis_prompt(self):
        return 'Данные, которые ты получил - это данные из docx документа технического задания на покупку изделия. Проанализируй их и верни данные в json, которые можно будет сравнить с другим json файлом характеристик. Верни эти данные строго в формате JSON. Используй только корректный JSON-объект без текста, пояснений, комментариев, markdown, кавычек вне структуры или лишних символов. Все значения должны быть извлечены из входных данных без искажения; отсутствующие значения указывай как null. В ответе должен быть только JSON, ничего больше.'

    def analyze(self, tz_data, prompt) -> Dict[str, Any]:
        try:
            full_prompt = f"{prompt}\n\nДанные:\n{tz_data}"
            if settings.LLM_PROVIDER == 'local': # костыль из за lm studio (или глупого меня)
                url = str(settings.LLM_API_URL).rstrip('/') + '/chat/completions'
                data = {
                    'model' : self.provider.model,
                    'messages':  [{
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

            return response.choices[0].message.content

        except Exception as e:
            raise ValueError(f"Ошибка: {str(e)}")


def analyze_tz_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    llm_provider = LLMProvider(settings.LLM_PROVIDER)
    analyzer = TzAnalyzer(llm_provider)
    return analyzer.analize_tz_file(file_path)







