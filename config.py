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

    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "admin")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "product_analyze")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    # Celery настройки
    CELERY_BROKER_URL: str = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    CELERY_RESULT_BACKEND: str = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")


settings = Settings()
if settings.DEBUG:
    print("=" * 60)
    print("🚀 КОНФИГУРАЦИЯ ПРИЛОЖЕНИЯ")
    print("=" * 60)
    print(f"📊 Database: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    print(f"🔴 Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")
    print(f"📁 Uploads: {settings.UPLOAD_DIR}")
    print(f"🌍 Environment: {settings.ENVIRONMENT}")
    print(f"🐛 Debug: {settings.DEBUG}")
    print("=" * 60)