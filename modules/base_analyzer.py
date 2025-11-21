from abc import abstractmethod

from modules.llm_provider import LLMProvider


class BaseAnalyzer:
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.client = provider.client
        self.model = provider.model
        self.max_tokens = provider.max_tokens

    @abstractmethod
    def create_analysis_prompt(self):
        pass
