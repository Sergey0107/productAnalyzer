import time
import json
import os
from pathlib import Path
from datetime import datetime
from celery import Task

from celery_app import celery_app
from db.database import SessionLocal
from models.models import Analysis, AnalysisStatus, FieldVerification
from services.tz_analyzer import analyze_tz_file
from services.passport_analyzer import analyze_passport_file
from services.comparator import json_compare_specifications
from utils.json_flattener import flatten_json


class DatabaseTask(Task):
    """Базовый класс для задач с автоматическим управлением сессией БД"""
    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(bind=True, base=DatabaseTask, name="tasks.process_analysis")
def process_analysis_task(self, analysis_id: int, tz_path: str, passport_path: str, comparison_mode: str):
    """
    Celery задача для обработки анализа

    Args:
        analysis_id: ID анализа в БД
        tz_path: путь к файлу ТЗ
        passport_path: путь к файлу паспорта
        comparison_mode: режим сравнения (flexible/strict)
    """
    start_time = time.time()

    # Обновляем статус задачи
    self.update_state(
        state='PROGRESS',
        meta={'status': 'Начало обработки...', 'progress': 0}
    )

    try:
        # Получаем анализ из БД
        analysis = self.db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            raise ValueError(f"Анализ с ID {analysis_id} не найден")

        # Шаг 1: Анализ ТЗ
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Анализ файла ТЗ...', 'progress': 20}
        )
        tz_data = analyze_tz_file(Path(tz_path))

        # Шаг 2: Анализ паспорта
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Анализ файла паспорта...', 'progress': 40}
        )
        passport_data = analyze_passport_file(Path(passport_path))

        # Шаг 3: Сглаживание данных
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Подготовка данных...', 'progress': 60}
        )
        tz_data_flat = flatten_json(tz_data)
        passport_data_flat = flatten_json(passport_data)

        # Шаг 4: Сравнение
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Сравнение спецификаций...', 'progress': 80}
        )
        comparison_result = json_compare_specifications(
            tz_data,
            passport_data,
            comparison_mode
        )

        # Шаг 5: Сохранение результатов
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Сохранение результатов...', 'progress': 90}
        )

        end_time = time.time()
        processing_time = int(end_time - start_time)

        analysis.tz_data = json.dumps(tz_data_flat, ensure_ascii=False)
        analysis.passport_data = json.dumps(passport_data_flat, ensure_ascii=False)
        analysis.comparison_result = json.dumps(comparison_result, ensure_ascii=False)
        analysis.processing_time = processing_time
        analysis.status = AnalysisStatus.COMPLETED
        analysis.completed_at = datetime.utcnow()

        # Создание записей проверки полей
        try:
            create_field_verifications_from_result(analysis_id, comparison_result, self.db)
        except Exception as e:
            print(f"Warning: Could not create field verifications: {e}")

        self.db.commit()

        # Завершение
        self.update_state(
            state='SUCCESS',
            meta={
                'status': 'Анализ завершен успешно',
                'progress': 100,
                'analysis_id': analysis_id,
                'processing_time': processing_time
            }
        )

        return {
            'status': 'completed',
            'analysis_id': analysis_id,
            'processing_time': processing_time
        }

    except Exception as e:
        # Обработка ошибок
        print(f"Error in process_analysis_task: {str(e)}")

        try:
            analysis = self.db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if analysis:
                analysis.status = AnalysisStatus.FAILED
                analysis.error_message = str(e)
                self.db.commit()
        except Exception as db_error:
            print(f"Error updating analysis status: {str(db_error)}")

        # Обновляем статус задачи
        self.update_state(
            state='FAILURE',
            meta={'status': f'Ошибка: {str(e)}', 'error': str(e)}
        )

        raise

    finally:
        # Очистка временных файлов
        try:
            if os.path.exists(tz_path):
                os.remove(tz_path)
            if os.path.exists(passport_path):
                os.remove(passport_path)
        except Exception as e:
            print(f"Error cleaning up files: {e}")


def create_field_verifications_from_result(analysis_id: int, comparison_result: dict, db):
    """Создает записи в field_verifications из результатов сравнения"""

    details = None

    if "details" in comparison_result:
        details = comparison_result["details"]
    elif "comparisons" in comparison_result:
        for item in comparison_result.get("comparisons", []):
            field_key = item.get("key", "")
            if field_key:
                field_verification = FieldVerification(
                    analysis_id=analysis_id,
                    field_key=field_key,
                    tz_value=str(item.get("tz_value", "")),
                    passport_value=str(item.get("passport_value", "")),
                    quote=item.get("quote", ""),
                    auto_match=item.get("match", None),
                    manual_verification=False,
                    specialist_comment=""
                )
                db.add(field_verification)
        return
    elif "response" in comparison_result:
        try:
            content = comparison_result["response"]["choices"][0]["message"]["content"]
            start = content.find('```json\n')
            end = content.find('\n```', start)
            if start != -1 and end != -1:
                json_str = content[start + 7:end]
                parsed_data = json.loads(json_str)
                details = parsed_data.get("details", {})
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            return

    if details:
        for field_key, field_data in details.items():
            auto_match = None
            if isinstance(field_data, dict):
                status = field_data.get("status")
                if status == "matched":
                    auto_match = True
                elif status in ["mismatched", "missing"]:
                    auto_match = False

                field_verification = FieldVerification(
                    analysis_id=analysis_id,
                    field_key=field_key,
                    tz_value=str(field_data.get("expected", "")),
                    passport_value=str(field_data.get("actual", "")),
                    quote=field_data.get("message", ""),
                    auto_match=auto_match,
                    manual_verification=False,
                    specialist_comment=""
                )
                db.add(field_verification)