FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей с очисткой кэша
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Обновление pip до последней версии
RUN pip install --upgrade pip setuptools wheel

# Копирование файлов зависимостей
COPY requirements.txt .

# Создание кэша pip
RUN pip cache purge

# Установка Python зависимостей с подробным выводом
RUN pip install --no-cache-dir -r requirements.txt \
    || (echo "Installing packages individually..." && \
        while read package; do \
            if [ -n "$package" ] && [[ ! "$package" =~ ^[[:space:]]*# ]]; then \
                echo "Installing: $package" && \
                pip install --no-cache-dir "$package" || exit 1; \
            fi; \
        done < requirements.txt)

# Копирование исходного кода
COPY . .

# Создание необходимых директорий
RUN mkdir -p /app/uploads /app/celery_data /app/static

# Создание пользователя для безопасности (опционально)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Порт приложения
EXPOSE 8000

# Команда по умолчанию
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]