"""
Быстрый скрипт для создания таблицы field_verifications
Запустите: python quick_create_table.py
"""

from database import engine, Base

print("=" * 60)
print("Создание таблицы field_verifications")
print("=" * 60)

try:
    # Создаем все таблицы из models.py
    print("\n1. Создаем таблицы из моделей...")
    Base.metadata.create_all(bind=engine)
    print("   ✓ Таблицы созданы успешно")

    # Проверяем, что таблица создана
    print("\n2. Проверяем созданные таблицы...")
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"   Найдено таблиц: {len(tables)}")
    for table in tables:
        print(f"   - {table}")

    if 'field_verifications' in tables:
        print("\n   ✓ Таблица field_verifications создана!")

        # Показываем структуру таблицы
        columns = inspector.get_columns('field_verifications')
        print("\n   Колонки таблицы:")
        for col in columns:
            print(f"   - {col['name']}: {col['type']}")
    else:
        print("\n   ✗ Таблица field_verifications НЕ создана!")
        print("   Проверьте файл models/models.py")

    print("\n" + "=" * 60)
    print("Готово!")
    print("=" * 60)

except Exception as e:
    print(f"\n✗ Ошибка: {e}")
    import traceback

    traceback.print_exc()