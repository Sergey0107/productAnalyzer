from celery import Celery
from config import settings

# Создаем экземпляр Celery
celery_app = Celery(
    "product_analyze",
    broker=f"redis://{getattr(settings, 'REDIS_HOST', 'localhost')}:{getattr(settings, 'REDIS_PORT', 6379)}/{getattr(settings, 'REDIS_DB', 0)}",
    backend=f"redis://{getattr(settings, 'REDIS_HOST', 'localhost')}:{getattr(settings, 'REDIS_PORT', 6379)}/{getattr(settings, 'REDIS_DB', 0)}",
    include=['tasks']
)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 минут максимум на задачу
    task_soft_time_limit=25 * 60,  # Мягкий лимит 25 минут
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    imports=['tasks.analysis_task'],
)

# Автоматическое обнаружение задач
celery_app.autodiscover_tasks(['tasks.analysis_task'])