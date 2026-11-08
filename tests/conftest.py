import io
import pytest

from app import create_app


@pytest.fixture()
def app():
    """Flask-приложение на лету с in-memory SQLite и тестовым клиентом."""
    app = create_app(database_url="sqlite:///:memory:")
    app.config["TESTING"] = True
    # Включаем получение исключений для отладки тестов, но у нас есть
    # глобальный JSON-обработчик — TESTING может его отключить, поэтому
    # обработаем ошибки вручную ниже.
    app.config["PROPAGATE_EXCEPTIONS"] = False
    with app.app_context():
        yield app


@pytest.fixture()
def client(app):
    """Test client для эндпоинтов."""
    return app.test_client()


# --- Вспомогательные данные ----------------------------------------------

CSV_SAMPLE = (
    "a,b,c\n"
    "1,10,foo\n"
    "2,20,bar\n"
    "2,20,bar\n"     # дубликат
    "3,,foo\n"       # пропущенное значение
).encode("utf-8")


EXCEL_SAMPLE = None  # заполним в фикстуре ниже


@pytest.fixture()
def xlsx_bytes():
    """CSV-данные, экспортированные в .xlsx, для проверки Excel-ветки."""
    import pandas as pd
    import io as _io
    df = pd.DataFrame({
        "a": [1.0, 2.0, 2.0, 3.0],
        "b": [10.0, 20.0, 20.0, None],
        "c": ["foo", "bar", "bar", "foo"],
    })
    buf = _io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def upload_csv(client, filename="data.csv", content=None):
    """Утилита: загружает CSV и возвращает (ответ, file_id)."""
    content = content if content is not None else CSV_SAMPLE
    resp = client.post(
        "/upload",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )
    return resp, (resp.get_json() or {}).get("file_id")