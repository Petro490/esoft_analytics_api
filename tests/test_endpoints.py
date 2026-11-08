"""Тесты stats, clean, plot, files и CRUD (включая каскадное удаление)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conftest import CSV_SAMPLE, upload_csv


# --- /data/stats ----------------------------------------------------------

def test_stats_ok(client):
    _, file_id = upload_csv(client)
    resp = client.get(f"/data/stats?file_id={file_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["file_id"] == file_id
    assert "mean" in body["analytics"]
    assert "median" in body["analytics"]
    assert "correlation" in body["analytics"]
    # mean по колонке a: (1+2+2+3)/4 = 2.0
    assert body["analytics"]["mean"]["a"] == 2.0


def test_stats_requires_file_id(client):
    resp = client.get("/data/stats")
    assert resp.status_code == 400
    assert "file_id обязателен" in resp.get_json()["error"]


def test_stats_file_not_found(client):
    resp = client.get("/data/stats?file_id=999")
    assert resp.status_code == 404


# --- /data/clean ----------------------------------------------------------

def test_clean_creates_copy(client):
    _, file_id = upload_csv(client)
    resp = client.post(f"/data/clean?file_id={file_id}")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["original_file_id"] == file_id
    assert body["cleaned_file_id"] == file_id + 1   # вторая запись в tables
    # В CSV_SAMPLE одна дублирующая строка ("2,20,bar")
    assert body["metrics"]["removed_duplicates_count"] == 1
    # Пропущенное значение в колонке b заполнено
    assert "b" in body["metrics"]["filled_columns"]


def test_clean_does_not_mutate_original(client):
    _, file_id = upload_csv(client)
    client.post(f"/data/clean?file_id={file_id}")
    # Исходный файл не меняется: скачиваем и убеждаемся, что байты те же
    resp = client.get(f"/data/file/{file_id}")
    assert resp.status_code == 200
    assert resp.data == CSV_SAMPLE


def test_clean_requires_file_id(client):
    resp = client.post("/data/clean")
    assert resp.status_code == 400


# --- /data/plot ------------------------------------------------------------

def test_plot_returns_png(client):
    _, file_id = upload_csv(client)
    resp = client.get(f"/data/plot?file_id={file_id}")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert resp.data.startswith(b"\x89PNG")


def test_plot_invalid_type(client):
    _, file_id = upload_csv(client)
    resp = client.get(f"/data/plot?file_id={file_id}&plot=bogus")
    assert resp.status_code == 400


def test_plot_hist_and_box(client):
    _, file_id = upload_csv(client)
    for plot_type in ("hist", "box"):
        resp = client.get(f"/data/plot?file_id={file_id}&plot={plot_type}")
        assert resp.status_code == 200
        assert resp.data.startswith(b"\x89PNG")


# --- /analyze (POST) ---------------------------------------------------------

def test_analyze_persists_result(client):
    _, file_id = upload_csv(client)
    resp = client.post(f"/analyze?file_id={file_id}&plot=hist")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["file_id"] == file_id
    assert body["plot_type"] == "hist"
    assert body["analysis_id"] == 1


# --- /files ---------------------------------------------------------------

def test_files_lists_uploads(client):
    upload_csv(client)
    upload_csv(client, filename="second.csv")
    resp = client.get("/files")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["count"] == 2
    assert len(body["files"]) == 2


# --- CRUD: upload / get / delete -------------------------------------------

def test_get_file_downloads_original(client):
    _, file_id = upload_csv(client)
    resp = client.get(f"/data/file/{file_id}")
    assert resp.status_code == 200
    assert resp.data == CSV_SAMPLE


def test_delete_file_cascades_analysis(client):
    _, file_id = upload_csv(client)
    client.post(f"/analyze?file_id={file_id}")
    # Перед удалением анализ существует
    assert client.get(f"/data/file/{file_id}").status_code == 200

    resp = client.delete(f"/data/file/{file_id}")
    assert resp.status_code == 200

    # После удаления файл (и связанные анализы) недоступны
    assert client.get(f"/data/file/{file_id}").status_code == 404
    assert client.get(f"/data/stats?file_id={file_id}").status_code == 404


def test_delete_nonexistent(client):
    resp = client.delete("/data/file/999")
    assert resp.status_code == 404