import os
from dotenv import load_dotenv


load_dotenv()


class Settings:

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER")

    LLM_API_KEY: str = os.getenv("LLM_API_KEY")

    LLM_MODEL: str = os.getenv("LLM_MODEL")

    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", 40900))

    LLM_API_URL: str = os.getenv("LLM_API_URL")

    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))

    UPLOAD_DIR: str = os.path.join(BASE_DIR, "uploads")

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    MAX_FILE_SIZE: int = 10 * 1024 * 1024

    ALLOWED_EXTENSIONS: set = {".pdf", ".docx", ".doc", ".txt"}


settings = Settings()
