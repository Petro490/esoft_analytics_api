"""Классы собственных исключений и глобальный обработчик ошибок JSON.

Цель — чтобы любая ошибка (включая 404/405/500) возвращалась в JSON,
а не в виде HTML-страницы Flask, и не раскрывала внутренности стека.
"""


class APIError(Exception):
    """Базовое бизнес-исключение с HTTP-статусом."""

    status_code = 400

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


# Удобные ярлыки для частых случаев
class NotFoundError(APIError):
    status_code = 404

class BadRequestError(APIError):
    status_code = 400

class UnsupportedMediaError(APIError):
    status_code = 415

class ProcessingError(APIError):
    status_code = 422

class EmptyNumericError(BadRequestError):
    """Файл загружен, но в нём нет числовых колонок для анализа."""
    def __init__(self, message="В файле отсутствуют числовые колонки для анализа"):
        super().__init__(message)