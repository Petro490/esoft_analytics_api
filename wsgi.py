"""Точка входа для WSGI-серверов (gunicorn/waitress).

Для gunicorn:  gunicorn --bind 0.0.0.0:8000 --workers 4 wsgi:app
Для waitress:  waitress-serve --port 8000 wsgi:app
"""
from dotenv import load_dotenv
load_dotenv()

from app import create_app

# Объект, который ожидает любой WSGI-сервер
app = create_app()