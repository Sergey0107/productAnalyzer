import sqlite3
from pathlib import Path


def add_new_columns():
    """Добавляет новые столбцы в существующую таблицу analyses"""
    db_path = Path("users.db")  # Укажите путь к вашей БД

    if not db_path.exists():
        print("База данных не найдена!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Проверяем, существуют ли уже эти столбцы
        cursor.execute("PRAGMA table_info(analyses)")
        columns = [column[1] for column in cursor.fetchall()]

        # Добавляем manual_verification, если его нет
        if 'manual_verification' not in columns:
            cursor.execute("""
                ALTER TABLE analyses 
                ADD COLUMN manual_verification BOOLEAN
            """)
            print("✓ Столбец 'manual_verification' добавлен")
        else:
            print("- Столбец 'manual_verification' уже существует")

        # Добавляем comment, если его нет
        if 'comment' not in columns:
            cursor.execute("""
                ALTER TABLE analyses 
                ADD COLUMN comment TEXT
            """)
            print("✓ Столбец 'comment' добавлен")
        else:
            print("- Столбец 'comment' уже существует")

        conn.commit()
        print("\n✓ Миграция выполнена успешно!")

    except Exception as e:
        print(f"\n✗ Ошибка при миграции: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    add_new_columns()