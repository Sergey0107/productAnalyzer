from typing import Optional

from openai import OpenAI
from config import settings


class LLMProvider:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider
        self._init_provider()


    def _init_provider(self):
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.api_url = settings.LLM_API_URL

        if self.api_key is None:
            print ('Тестовое исключение')



        if not self.api_key:
            raise ValueError(
                f"API ключ не найден для провайдера '{self.provider}'! "
                f"Проверьте настройку LLM_API_KEY в .env файле."
            )

        if self.provider == "local":
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_url
            )
        elif self.provider == "openrouter":
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1"
            )
        else:
            self.client = OpenAI(api_key=self.api_key)

