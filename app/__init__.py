from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from app import database
from app.errors import APIError
from app.routes import analytics_bp


def create_app(database_url: str | None = None):
    app = Flask(__name__)

    # Конфигурация приложения
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 МБ лимит на загрузку

    # Отдавать кириллицу в JSON как есть, без \uXXXX экранирования
    app.json.ensure_ascii = False

    # Инициализация БД: создаём engine и сессию из переданного URL
    # (или из переменных окружения, если URL не передан).
    engine = database.get_engine(database_url)
    app.config["SESSION_FACTORY"] = database.create_session_factory(engine)
    database.init_db(bind=engine)

    # Регистрируем Blueprint эндпоинтов
    app.register_blueprint(analytics_bp)

    # ---- Глобальная обработка ошибок в JSON (вместо HTML-страниц Flask) ----
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return jsonify({"error": err.message}), err.status_code

    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(413)  # файл больше MAX_CONTENT_LENGTH
    def handle_http_errors(err: HTTPException):
        return jsonify({"error": err.description}), err.code

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        # Не раскрываем пользователю детали внутренней ошибки
        app.logger.exception("Unhandled exception")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500

    return app