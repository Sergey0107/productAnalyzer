import base64
import json
import time
from typing import List, Dict, Any

import requests

from config import settings
from llm.llm_provider import LLMProvider
from services import prompts_service


class LLMService:
    def __init__(self):
        self.provider = LLMProvider()
        self.client = self.provider.client
        self.model = self.provider.model
        self.max_tokens = self.provider.max_tokens

    def extract_characteristics_via_llm(self, input_data, prompt):
        try:
            if self._is_image_batch(input_data):
                accumulated_data = {}

                batches = self._split_into_batches(input_data, 1)

                print(f"[DEBUG] Обработка {len(batches)} батчей")

                for batch_idx, batch in enumerate(batches):
                    batch_start = time.time()

                    is_first_batch = (batch_idx == 0)

                    if is_first_batch:
                        current_prompt = prompt
                    else:
                        current_prompt = prompts_service._create_passport_iterative_prompt(accumulated_data, prompt)

                    response = self._analyze_images_batch(batch, current_prompt)

                    new_data = self._parse_json_response(response)
                    accumulated_data = self._merge_data(accumulated_data, new_data)

                    batch_elapsed = time.time() - batch_start
                    print(f"[DEBUG] Батч {batch_idx + 1}/{len(batches)} | time={batch_elapsed:.2f}s | характеристик={len(accumulated_data)}")
                return accumulated_data

            full_prompt = f"{prompt}\n\nДанные:\n{input_data}"
            prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
            data_preview = str(input_data)[:100] + "..." if len(str(input_data)) > 100 else str(input_data)

            if settings.LLM_PROVIDER == 'local':
                url = str(settings.LLM_API_URL).rstrip('/') + '/chat/completions'
                data = {
                    'model': self.provider.model,
                    'messages': [{
                        "role": "user",
                        "content": full_prompt,
                    }]
                }

                print(f"[DEBUG] LLM запрос | model={self.provider.model} | type=text | prompt='{prompt_preview}' | data='{data_preview}'")

                llm_start = time.time()
                response = requests.post(url, json=data)
                llm_elapsed = time.time() - llm_start

                result = response.json()

                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                result_preview = content[:150] + "..." if len(content) > 150 else content
                print(f"[DEBUG] LLM ответ | time={llm_elapsed:.2f}s | length={len(content)} | preview='{result_preview}'")

                return self._parse_json_response(content)

            elif settings.LLM_PROVIDER == 'openrouter':

                data = {
                    "model": self.model,
                    "messages": [{
                        "role": "user",
                        "content": full_prompt
                    }],
                    "temperature": 0.01
                }

                headers = {
                    "Authorization": f"Bearer {self.provider.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "productAnalyze",
                    "X-Title": "ProductAnalyze"
                }

                print(f"[DEBUG] LLM запрос | model={self.model} | type=text | prompt='{prompt_preview}' | data='{data_preview}'")

                llm_start = time.time()
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    data=json.dumps(data),
                    timeout=300
                )
                llm_elapsed = time.time() - llm_start

                if response.status_code != 200:
                    print(f"[DEBUG] Ошибка {response.status_code}: {response.text[:500]}")

                response.raise_for_status()

                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                result_preview = content[:150] + "..." if len(content) > 150 else content
                print(f"[DEBUG] LLM ответ | time={llm_elapsed:.2f}s | length={len(content)} | preview='{result_preview}'")

                return self._parse_json_response(content)


            messages = [{
                "role": "user",
                "content": full_prompt
            }]

            print(f"[DEBUG] LLM запрос | model={self.model} | type=text | prompt='{prompt_preview}' | data='{data_preview}'")

            llm_start = time.time()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            llm_elapsed = time.time() - llm_start

            result = response.choices[0].message.content
            result_preview = result[:150] + "..." if len(result) > 150 else result
            print(f"[DEBUG] LLM ответ | time={llm_elapsed:.2f}s | length={len(result)} | preview='{result_preview}'")

            return self._parse_json_response(result)

        except Exception as e:
            raise ValueError(f"Ошибка: {str(e)}")


    def _split_into_batches(self, items: List, batch_size: int) -> List[List]:
        return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

    def _check_llm_connection(self) -> None:
        print("[DEBUG] Проверка соединения с LLM...")

        try:
            if settings.LLM_PROVIDER == 'local':
                self._check_local_connection()
            elif settings.LLM_PROVIDER == 'openrouter':
                self._check_openrouter_connection()
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

    def _check_openrouter_connection(self) -> None:

        print(f"[DEBUG] Проверка OpenRouter API...")
        print(f"[DEBUG] Модель: {self.model}")

        try:

            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1
            }

            headers = {
                "Authorization": f"Bearer {self.provider.api_key}",
            }

            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                data=json.dumps(data),
                timeout=30
            )

            if response.status_code == 200:
                print(f"[DEBUG] OpenRouter API доступен")
                print(f"[DEBUG]  Модель '{self.model}' работает корректно")
            else:
                raise ConnectionError(f"Ошибка {response.status_code}: {response.text[:500]}")

        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Не удалось подключиться к OpenRouter API: {str(e)}")
        except Exception as e:
            raise ConnectionError(f"Не удалось подключиться к OpenRouter API: {str(e)}")

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


    def _is_image_batch(self, data):

        if isinstance(data, list):
            if all(isinstance(x, (bytes, bytearray)) for x in data):
                return True

            if all(isinstance(x, str) and x.startswith("data:image") for x in data):
                return True

            if all(isinstance(x, dict) and "image_url" in x for x in data):
                return True

        return False

    def _analyze_images_batch(self, images: List[bytes], prompt: str) -> str:

        try:
            if settings.LLM_PROVIDER == 'local':
                return self._analyze_local(images, prompt)
            elif settings.LLM_PROVIDER == 'openrouter':
                return self._analyze_openrouter(images, prompt)
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
            # Определяем формат изображения по сигнатуре
            image_format = "image/png" if img_bytes.startswith(b'\x89PNG') else "image/jpeg"
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_format};base64,{base64_image}"
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

        prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
        print(f"[DEBUG] LLM запрос | model={self.provider.model} | images={len(images)} | prompt='{prompt_preview}'")

        llm_start = time.time()
        response = requests.post(url, json=data, headers=headers, timeout=300)
        llm_elapsed = time.time() - llm_start

        if response.status_code != 200:
            print(f"[DEBUG] Ошибка {response.status_code}: {response.text[:500]}")

        response.raise_for_status()

        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')

        content_preview = content[:150] + "..." if len(content) > 150 else content
        print(f"[DEBUG] LLM ответ | time={llm_elapsed:.2f}s | length={len(content)} | preview='{content_preview}'")

        return content

    def _analyze_openai(self, images: List[bytes], prompt: str) -> str:
        content = [{"type": "text", "text": prompt}]

        for img_bytes in images:
            base64_image = base64.b64encode(img_bytes).decode('utf-8')

            image_format = "image/png" if img_bytes.startswith(b'\x89PNG') else "image/jpeg"
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_format};base64,{base64_image}",
                    "detail": "high"  # high detail для лучшего распознавания текста
                }
            })

        kwargs = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}]
        }

        prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
        print(f"[DEBUG] LLM запрос | model={self.model} | images={len(images)} | prompt='{prompt_preview}'")

        llm_start = time.time()
        response = self.client.chat.completions.create(**kwargs)
        llm_elapsed = time.time() - llm_start

        result = response.choices[0].message.content

        result_preview = result[:150] + "..." if len(result) > 150 else result
        print(f"[DEBUG] LLM ответ | time={llm_elapsed:.2f}s | length={len(result)} | preview='{result_preview}'")

        return result

    def _analyze_openrouter(self, images: List[bytes], prompt: str) -> str:

        content = [{"type": "text", "text": prompt}]

        for img_bytes in images:
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            image_format = "image/png" if img_bytes.startswith(b'\x89PNG') else "image/jpeg"
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_format};base64,{base64_image}"
                }
            })

        data = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": content
            }],
            "temperature": 0.01
        }

        headers = {
            "Authorization": f"Bearer {self.provider.api_key}",
            "Content-Type": "application/json",
        }

        prompt_preview = prompt[:100] + "..." if len(prompt) > 100 else prompt
        print(f"[DEBUG] LLM запрос | model={self.model} | images={len(images)} | prompt='{prompt_preview}'")

        llm_start = time.time()
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(data),
            timeout=300
        )
        llm_elapsed = time.time() - llm_start

        if response.status_code != 200:
            print(f"[DEBUG] Ошибка {response.status_code}: {response.text[:500]}")

        response.raise_for_status()

        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')

        content_preview = content[:150] + "..." if len(content) > 150 else content
        print(f"[DEBUG] LLM ответ | time={llm_elapsed:.2f}s | length={len(content)} | preview='{content_preview}'")

        return content

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

            return data
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
