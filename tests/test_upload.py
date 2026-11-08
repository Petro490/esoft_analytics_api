"""Тесты эндпоинта /upload: коды 201, 400 и 415."""
import io
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conftest import CSV_SAMPLE, upload_csv


def test_index_returns_service_info(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["name"] == "Data Analytics REST API"
    assert "endpoints" in body
    assert "POST /upload" in body["endpoints"]


def test_unknown_route_returns_json_404(client):
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_upload_csv_ok(client):
    resp, file_id = upload_csv(client)
    assert resp.status_code == 201
    assert resp.get_json()["message"] == "Файл успешно загружен и сохранён в PostgreSQL"
    assert file_id == 1


def test_upload_no_file_key(client):
    resp = client.post("/upload", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert "Файл не передан" in resp.get_json()["error"]


def test_upload_empty_filename(client):
    resp = client.post(
        "/upload",
        data={"file": (io.BytesIO(CSV_SAMPLE), "")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "Пустое имя файла" in resp.get_json()["error"]


def test_upload_unsupported_media(client):
    resp = client.post(
        "/upload",
        data={"file": (io.BytesIO(b"whatever"), "data.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 415
    assert "Неподдерживаемый тип медиа" in resp.get_json()["error"]


def test_upload_xlsx_ok(client, xlsx_bytes):
    resp = client.post(
        "/upload",
        data={"file": (io.BytesIO(xlsx_bytes), "data.xlsx")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    assert resp.get_json()["file_id"] == 1