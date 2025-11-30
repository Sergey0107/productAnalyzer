import requests
from typing import Dict, Any, Union
from pathlib import Path
from docx import Document

from config import settings
from llm import llm_service
from llm.llm_service import LLMService
from services import prompts_service
from handlers.file_handler import FileHandler
from services.base_analyzer import BaseAnalyzer
from llm.llm_provider import LLMProvider


class TzAnalyzer(BaseAnalyzer):

    def analize_tz_file(self, file_path):
        file_handler = FileHandler()
        llm_service = LLMService()
        tz_data = file_handler.get_data_from_file(file_path)
        prompt = prompts_service.get_tz_analyze_prompt()
        return llm_service.extract_characteristics_via_llm(tz_data, prompt)


def analyze_tz_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    llm_provider = LLMProvider(settings.LLM_PROVIDER)
    analyzer = TzAnalyzer(llm_provider)
    return analyzer.analize_tz_file(file_path)







