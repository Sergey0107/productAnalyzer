from db.database import engine, Base
from models.models import User, Analysis, FieldVerification

def create_tables():
    """Создает все таблицы в базе данных"""
    Base.metadata.create_all(bind=engine)
    print("Таблицы успешно созданы!")

if __name__ == "__main__":
    create_tables()