"""
Скрипт для миграции существующих данных в field_verifications
"""
import sys
import os
from pathlib import Path
import json

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from db.database import SessionLocal
from models.models import Analysis, FieldVerification


def migrate_all_analyses():
    """Мигрирует все завершенные анализы"""
    db = SessionLocal()

    try:
        # Получаем все завершенные анализы с comparison_result
        analyses = db.query(Analysis).filter(
            Analysis.status == 'COMPLETED',
            Analysis.comparison_result.isnot(None)
        ).all()

        print(f"Найдено {len(analyses)} анализов для миграции")

        migrated_count = 0

        for analysis in analyses:
            try:
                # Парсим comparison_result
                comparison_data = json.loads(analysis.comparison_result)

                # Проверяем, есть ли уже записи для этого анализа
                existing_count = db.query(FieldVerification).filter(
                    FieldVerification.analysis_id == analysis.id
                ).count()

                if existing_count > 0:
                    print(f"  Анализ #{analysis.id}: уже есть {existing_count} записей, пропускаем")
                    continue

                # Создаем записи (используем функцию из main.py)
                from main import create_field_verifications_from_result
                create_field_verifications_from_result(analysis.id, comparison_data, db)

                migrated_count += 1
                print(f"  Анализ #{analysis.id}: мигрирован")

            except Exception as e:
                print(f"  ⚠ Ошибка при миграции анализа #{analysis.id}: {str(e)}")
                continue

        db.commit()
        print(f"\n✓ Успешно мигрировано {migrated_count} анализов")

        # Проверяем результат
        total_fv = db.query(FieldVerification).count()
        print(f"✓ Всего записей в field_verifications: {total_fv}")

        return migrated_count

    except Exception as e:
        db.rollback()
        print(f"✗ Ошибка при миграции: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Миграция данных в field_verifications")
    print("=" * 60)

    response = input("Выполнить миграцию? (y/n): ")

    if response.lower() in ['y', 'yes', 'д', 'да']:
        migrated = migrate_all_analyses()
        print(f"\nМигрировано анализов: {migrated}")
    else:
        print("Миграция отменена")

    print("\n" + "=" * 60)
    print("Завершено")
    print("=" * 60)