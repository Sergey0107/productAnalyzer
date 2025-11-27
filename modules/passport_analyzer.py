import base64
import json
import io
import time
import fitz
from pathlib import Path
from typing import Dict, Any, Union, List, Optional

import requests
from PIL import Image

from config import settings
from modules.base_analyzer import BaseAnalyzer
from modules.llm_provider import LLMProvider


class PassportAnalyzer(BaseAnalyzer):

    PAGES_PER_REQUEST: int = 1

    def __init__(self, provider, pages_per_request: int = 1):
        super().__init__(provider)
        self.pages_per_request = pages_per_request

    def analyze_passport_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:

        file_path = Path(file_path)

        self._check_llm_connection()

        images = self._pdf_to_images(file_path)

        if not images:
            raise ValueError("Не удалось извлечь изображения из PDF")

        print(f"[DEBUG] PDF конвертирован: {len(images)} страниц")


        accumulated_data = {}


        batches = self._split_into_batches(images, self.pages_per_request)

        print(f"[DEBUG] Разбито на {len(batches)} батчей по {self.pages_per_request} страниц")

        for batch_idx, batch in enumerate(batches):
            print(f"[DEBUG] Обработка батча {batch_idx + 1}/{len(batches)}...")

            start_time = time.time()

            is_first_batch = (batch_idx == 0)

            prompt = self._create_iterative_prompt(accumulated_data, is_first_batch)

            response = self._analyze_images_batch(batch, prompt)

            new_data = self._parse_json_response(response)
            accumulated_data = self._merge_data(accumulated_data, new_data)

            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"[DEBUG] Батч {batch_idx + 1} обработан за {elapsed_time:.2f} сек. Найдено новых характеристик: {len(accumulated_data)}")

        return accumulated_data

    def _check_llm_connection(self) -> None:
        print("[DEBUG] Проверка соединения с LLM...")

        try:
            if settings.LLM_PROVIDER == 'local':
                self._check_local_connection()
            else:
                self._check_openai_connection()
            print("[DEBUG]  Соединение с LLM установлено успешно")
        except Exception as e:
            print(f"[DEBUG]  Ошибка соединения с LLM: {str(e)}")
            raise

    def _check_local_connection(self) -> None:

        base_url = str(settings.LLM_API_URL).rstrip('/')
        models_url = base_url.replace('/chat/completions', '').rstrip('/') + '/models'

        urls_to_try = [
            models_url,
            base_url.rsplit('/v1', 1)[0] + '/v1/models' if '/v1' in base_url else None
        ]
        urls_to_try = [u for u in urls_to_try if u]

        print(f"[DEBUG] Проверка локального LLM: {base_url}")

        for url in urls_to_try:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    models = data.get('data', [])

                    print(f"[DEBUG] Доступные модели ({len(models)}):")
                    for model in models:
                        model_id = model.get('id', 'unknown')
                        print(f"[DEBUG]   - {model_id}")


                    model_ids = [m.get('id', '') for m in models]
                    if self.provider.model and self.provider.model not in model_ids:
                        print(f"[DEBUG] Модель '{self.provider.model}' не найдена в списке")

                    return
            except requests.exceptions.RequestException:
                continue

        raise ConnectionError(f"Не удалось подключиться к локальному LLM: {base_url}")

    def _check_openai_connection(self) -> None:

        print(f"[DEBUG] Проверка OpenAI API...")
        print(f"[DEBUG] Модель: {self.model}")

        try:

            models = self.client.models.list()
            print(f"[DEBUG] OpenAI API доступен")

            model_ids = [m.id for m in models.data]
            if self.model and self.model not in model_ids:

                print(f"[DEBUG]  Модель '{self.model}' не в списке стандартных моделей")
            else:
                print(f"[DEBUG]  Модель '{self.model}' доступна")

        except Exception as e:
            raise ConnectionError(f"Не удалось подключиться к OpenAI API: {str(e)}")

    def _pdf_to_images(self, file_path: Path) -> List[bytes]:
        images = self._pdf_to_images_pymupdf(file_path)
        return images

    def _pdf_to_images_pymupdf(self, file_path: Path) -> List[bytes]:

        images = []
        doc = fitz.open(file_path)

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)

            mat = fitz.Matrix(1.5, 1.5)
            pix = page.get_pixmap(matrix=mat)

            img_bytes = self._compress_image(pix.tobytes("png"))
            images.append(img_bytes)

        doc.close()
        return images


    def _compress_image(self, png_bytes: bytes, max_size: int = 768, quality: int = 70) -> bytes:
        img = Image.open(io.BytesIO(png_bytes))

        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img = img.convert('RGB')
        img.save(buffer, format='JPEG', quality=quality, optimize=True)

        return buffer.getvalue()

    def _split_into_batches(self, items: List, batch_size: int) -> List[List]:
        return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

    def _create_iterative_prompt(self, accumulated_data: Dict, is_first_batch: bool) -> str:

        base_prompt = (
            "Проанализируй изображения страниц технического паспорта изделия. "
            "Извлеки все технические характеристики.\n\n"
            "Правила:\n"
            "- Верни данные строго в формате JSON\n"
            "- Ключ — название характеристики (не изменяй названия)\n"
            "- Значение — числовое или текстовое значение\n"
            "- Сохраняй единицы измерения\n"
            "- Если значение отсутствует — укажи null\n"
            "- Не придумывай данные\n"
            "- В ответе должен быть ТОЛЬКО валидный JSON"
        )

        if is_first_batch:
            return base_prompt

        return (
            f"{base_prompt}\n\n"
            f"Уже извлечённые характеристики из предыдущих страниц:\n"
            f"```json\n{json.dumps(accumulated_data, ensure_ascii=False, indent=2)}\n```\n\n"
            f"Дополни этот JSON новыми характеристиками с текущих страниц. "
            f"Если характеристика уже есть — обнови значение только если новое более полное или точное. "
            f"Верни полный обновлённый JSON."
        )

    def _analyze_images_batch(self, images: List[bytes], prompt: str) -> str:

        try:
            if settings.LLM_PROVIDER == 'local':
                return self._analyze_local(images, prompt)
            else:
                return self._analyze_openai(images, prompt)
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            if e.response is not None:
                try:
                    error_detail = e.response.text
                except:
                    pass
            raise ValueError(f"Ошибка при анализе изображений: {str(e)}\nДетали: {error_detail}")
        except Exception as e:
            raise ValueError(f"Ошибка при анализе изображений: {str(e)}")

    def _analyze_local(self, images: List[bytes], prompt: str) -> str:

        url = str(settings.LLM_API_URL).rstrip('/') + '/chat/completions'

        content = []

        for img_bytes in images:
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })

        content.append({"type": "text", "text": prompt})

        data = {
            "model": self.provider.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 4096,
            "temperature": 0.1,
            "stream": False
        }

        headers = {"Content-Type": "application/json"}

        print(f"[DEBUG] Отправка запроса к {url}")
        print(f"[DEBUG] Модель: {self.provider.model}")
        print(f"[DEBUG] Количество изображений: {len(images)}")

        response = requests.post(url, json=data, headers=headers, timeout=300)

        if response.status_code != 200:
            print(f"[DEBUG] Ошибка {response.status_code}: {response.text[:500]}")

        response.raise_for_status()

        result = response.json()
        return result.get('choices', [{}])[0].get('message', {}).get('content', '')

    def _analyze_openai(self, images: List[bytes], prompt: str) -> str:

        content = [{"type": "text", "text": prompt}]

        for img_bytes in images:
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                    "detail": "high"
                }
            })

        kwargs = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}]
        }

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _parse_json_response(self, response: str) -> Dict[str, Any]:

        if not response:
            return {}

        response = response.strip()

        if response.startswith('```'):
            lines = response.split('\n')
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith('```') and not in_json:
                    in_json = True
                    continue
                if line.startswith('```') and in_json:
                    break
                if in_json:
                    json_lines.append(line)
            response = '\n'.join(json_lines)

        try:
            data = json.loads(response)
            if isinstance(data, list):
                merged = {}
                for item in data:
                    if isinstance(item, dict):
                        merged.update(item)
                return merged

            return json.loads(response)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            return {}

    def _merge_data(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        result = existing.copy()


        for key, value in new.items():
            if key not in result:
                # Новый ключ — добавляем
                result[key] = value
            elif result[key] is None and value is not None:
                # Существующее значение null, новое не null — обновляем
                result[key] = value
            elif isinstance(value, str) and isinstance(result[key], str):
                # Оба строки — берём более длинную (более полную)
                if len(value) > len(result[key]):
                    result[key] = value
            elif isinstance(value, dict) and isinstance(result[key], dict):
                # Оба словари — рекурсивный мерж
                result[key] = self._merge_data(result[key], value)
            # В остальных случаях оставляем существующее значение

        return result

    def analyze(self, file_path, prompt):
        return self.analyze_passport_file(file_path)

    def create_analysis_prompt(self):

        return self._create_iterative_prompt({}, is_first_batch=True)


def analyze_passport_file(
        file_path: Union[str, Path],
        pages_per_request: int = 1
) -> Dict[str, Any]:
    llm_provider = LLMProvider(settings.LLM_PROVIDER)
    analyzer = PassportAnalyzer(llm_provider, pages_per_request=pages_per_request)
    return analyzer.analyze_passport_file(file_path)