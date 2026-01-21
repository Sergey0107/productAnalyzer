# db/migration.py
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
import sys

# Добавляем путь к корню проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import Base
from models.models import User, Analysis, FieldVerification

load_dotenv()


def is_running_in_container():
    """Проверяем, запущен ли скрипт внутри Docker контейнера"""
    return os.path.exists('/.dockerenv')


def get_postgres_host():
    """Определяем правильный хост для PostgreSQL в зависимости от окружения"""
    if is_running_in_container():
        # Внутри контейнера используем имя сервиса из docker-compose
        return "db"
    else:
        # На хосте используем localhost
        return "localhost"


def create_database():
    """Создает базу данных если она не существует"""

    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_password = os.getenv("POSTGRES_PASSWORD", "admin")
    db_host = get_postgres_host()  # Используем правильный хост
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "product_analyze")  # Исправлено: product_analyze вместо product_analyzer

    print(f"🔍 Проверка базы данных '{db_name}'...")
    print(f"📡 Подключение к {db_host}:{db_port}...")

    # Подключаемся к postgres для создания БД
    try:
        admin_conn = psycopg2.connect(
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            database="postgres",
            connect_timeout=10
        )
        admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        with admin_conn.cursor() as cursor:
            # Проверяем существование БД
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
            exists = cursor.fetchone()

            if not exists:
                print(f"📦 Создание базы данных '{db_name}'...")
                cursor.execute(f"CREATE DATABASE {db_name}")
                print(f"✅ База данных '{db_name}' создана")
            else:
                print(f"📊 База данных '{db_name}' уже существует")

        admin_conn.close()
        return True

    except psycopg2.OperationalError as e:
        print(f"❌ Ошибка подключения к PostgreSQL: {e}")
        print(f"Подробности: host={db_host}, port={db_port}, user={db_user}")
        print("\nУбедитесь что:")
        if is_running_in_container():
            print("1. Сервис 'db' запущен в Docker Compose")
            print("2. PostgreSQL контейнер готов принимать подключения")
            print("3. Сеть 'app_network' создана правильно")
        else:
            print("1. PostgreSQL запущен локально")
            print("2. Правильные параметры в .env файле")
            print(f"3. Можно подключиться: psql -h {db_host} -p {db_port} -U {db_user} -d postgres")
        return False


def create_tables():
    """Создает все таблицы в базе данных"""

    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_password = os.getenv("POSTGRES_PASSWORD", "password")
    db_host = get_postgres_host()  # Используем правильный хост
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "product_analyze")

    # Строка подключения для SQLAlchemy
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    try:
        # Создаем движок для работы с таблицами
        engine = create_engine(database_url)

        print(f"🔄 Создание таблиц в базе данных '{db_name}'...")

        # Проверяем существование таблиц
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            existing_tables = [row[0] for row in result.fetchall()]

            if existing_tables:
                print(f"📊 Найдены существующие таблицы: {', '.join(existing_tables)}")
                print("ℹ️  Таблицы уже созданы, пропускаем создание.")
                return True

        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)

        print("✅ Таблицы успешно созданы:")
        for table in Base.metadata.tables.values():
            print(f"   - {table.name}")

        return True

    except Exception as e:
        print(f"❌ Ошибка при создании таблиц: {e}")
        return False


def seed_database():
    """Создает тестовые данные (опционально)"""

    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_password = os.getenv("POSTGRES_PASSWORD", "password")
    db_host = get_postgres_host()
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "product_analyze")

    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    engine = create_engine(database_url)

    from sqlalchemy.orm import sessionmaker
    from db.security import get_password_hash

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Проверяем, есть ли уже пользователи
        existing_user = db.query(User).filter(User.username == "admin").first()
        if not existing_user:
            # Создаем тестового пользователя
            admin_user = User(
                username="admin",
                email="admin@example.com",
                password_hash=get_password_hash("admin123")
            )
            db.add(admin_user)
            db.commit()
            print("✅ Тестовый пользователь создан:")
            print(f"   Логин: admin")
            print(f"   Пароль: admin123")
        else:
            print("ℹ️  Пользователь 'admin' уже существует")

    except Exception as e:
        print(f"❌ Ошибка при создании тестовых данных: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 МИГРАЦИЯ БАЗЫ ДАННЫХ")
    print("=" * 60)

    if is_running_in_container():
        print("📦 Запущено внутри Docker контейнера")
        print(f"📡 Хост PostgreSQL: {get_postgres_host()}")
    else:
        print("💻 Запущено на хосте")
        print(f"📡 Хост PostgreSQL: {get_postgres_host()}")

    # Обработка аргументов командной строки
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "init":
            print("\n🔧 Инициализация базы данных...")
            if create_database():
                create_tables()
                seed_database()

        elif command == "seed":
            print("\n🌱 Создание тестовых данных...")
            seed_database()

        elif command == "create-db":
            print("\n📦 Создание базы данных...")
            create_database()

        elif command == "create-tables":
            print("\n🔄 Создание таблиц...")
            create_tables()

        else:
            print(f"❌ Неизвестная команда: {command}")
            print("\nДоступные команды:")
            print("  init        - создать БД, таблицы и тестовые данные")
            print("  create-db   - только создать БД")
            print("  create-tables - только создать таблицы")
            print("  seed        - создать тестовые данные")
    else:
        # По умолчанию создаем БД и таблицы
        print("\n🔧 Запуск инициализации по умолчанию...")
        if create_database():
            create_tables()