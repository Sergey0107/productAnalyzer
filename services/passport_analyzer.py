import base64
import json
import io
import time
import fitz
from pathlib import Path
from typing import Dict, Any, Union, List

import requests
from PIL import Image

from config import settings
from handlers.file_handler import FileHandler
from llm.llm_service import LLMService
from services import prompts_service
from services.base_analyzer import BaseAnalyzer
from llm.llm_provider import LLMProvider


class PassportAnalyzer(BaseAnalyzer):

    def __init__(self, provider, pages_per_request: int = 1):
        super().__init__(provider)
        self.pages_per_request = pages_per_request

    def analyze_passport_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:

        file_path = Path(file_path)
        file_handler = FileHandler()
        llm_service = LLMService()
        passport_data = file_handler.get_data_from_file(file_path)
        prompt = prompts_service.get_passport_initial_analyze_prompt()
        llm_service._check_llm_connection()
        return llm_service.extract_characteristics_via_llm(passport_data, prompt)



def analyze_passport_file(
        file_path: Union[str, Path],
        pages_per_request: int = 1
) -> Dict[str, Any]:
    llm_provider = LLMProvider(settings.LLM_PROVIDER)
    analyzer = PassportAnalyzer(llm_provider, pages_per_request=pages_per_request)
    return analyzer.analyze_passport_file(file_path)