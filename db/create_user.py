# db/create_user.py
import sys
import os

from db.security import hash_password

# Добавляем корень проекта в путь Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.models import User
from db.database import engine, SessionLocal, Base

# Создаем таблицы если их нет
Base.metadata.create_all(bind=engine)

# Создаем сессию
db = SessionLocal()

try:
    # Проверяем, существует ли уже пользователь
    existing_user = db.query(User).filter(User.username == "admin").first()

    if not existing_user:
        # Создаем пользователя
        new_user = User(
            username="admin",
            password_hash=hash_password("1234")
        )
        db.add(new_user)
        db.commit()
        print("✅ Пользователь 'admin' создан успешно!")
        print("   Логин: admin")
        print("   Пароль: 1234")
    else:
        print("ℹ️  Пользователь 'admin' уже существует")

except Exception as e:
    print(f"❌ Ошибка при создании пользователя: {e}")
    db.rollback()
finally:
    db.close()
print("User created")
