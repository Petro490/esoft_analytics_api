# --- Продакшн-образ: gunicorn + Python 3.11 ---
FROM python:3.11-slim

# Запрещаем Python писать .pyc и буферизовать stdout (важно для логов в контейнере)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Сначала копируем requirements и ставим зависимости (слой кэшируется)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходники приложения
COPY . .

# Слушaть порт, который открываем в docker-compose
EXPOSE 8000

# Запускаем через gunicorn (4 воркера, слушает 0.0.0.0:8000)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "wsgi:app"]