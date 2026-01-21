from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем строку подключения из переменных окружения
# Формат: postgresql://user:password@host:port/database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:admin@localhost:5432/product_analyzer"
)

# Создаем движок для PostgreSQL
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Проверка соединения перед использованием
    pool_size=10,        # Размер пула соединений
    max_overflow=20,     # Максимальное количество соединений сверх pool_size
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# Функция для получения сессии (удобно для зависимостей FastAPI)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()