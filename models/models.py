from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from db.database import Base
from datetime import datetime
import enum


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)


class AnalysisStatus(enum.Enum):
    PENDING = "pending"  # Ожидает обработки
    PROCESSING = "processing"  # В обработке
    COMPLETED = "completed"  # Завершено
    FAILED = "failed"  # Ошибка


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Названия файлов
    tz_filename = Column(String(255), nullable=False)
    passport_filename = Column(String(255), nullable=False)

    # Режим сравнения
    comparison_mode = Column(String(50), default="flexible")

    # Статус
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)

    # Результаты (JSON)
    tz_data = Column(Text, nullable=True)
    passport_data = Column(Text, nullable=True)
    comparison_result = Column(Text, nullable=True)

    # Общая ручная проверка и комментарий
    manual_verification = Column(Boolean, nullable=True)
    comment = Column(Text, nullable=True)

    # Метаданные
    processing_time = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Связь с пользователем
    user = relationship("User", backref="analyses")


class FieldVerification(Base):
    """Модель для хранения полных данных сравнения и ручной проверки по каждому полю"""
    __tablename__ = "field_verifications"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)

    # Идентификация поля
    field_key = Column(String(500), nullable=False)  # Ключ поля (название характеристики)

    # Данные из документов
    tz_value = Column(Text, nullable=True)  # Значение из технического задания
    passport_value = Column(Text, nullable=True)  # Значение из паспорта
    quote = Column(Text, nullable=True)  # Цитата из документа

    # Результат автоматической проверки
    auto_match = Column(Boolean, nullable=True)  # Результат автоматического сравнения

    # Ручная проверка специалиста
    manual_verification = Column(Boolean, nullable=True)  # True = верно, False = не верно, None = не проверено
    specialist_comment = Column(Text, nullable=True)  # Комментарий специалиста

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связь с анализом
    analysis = relationship("Analysis", backref="field_verifications")