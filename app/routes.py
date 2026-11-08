import os

from flask import Blueprint, request, jsonify, send_file, current_app

from app import services
from app.errors import (APIError, BadRequestError, NotFoundError,
                        UnsupportedMediaError, ProcessingError)
from app.database import create_session_factory, get_engine
from app.models import UploadedFileDB, AnalysisResultDB

analytics_bp = Blueprint("analytics", __name__)

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}
ALLOWED_PLOT_TYPES = {"corr", "hist", "box"}

SERVICE_INFO = {
    "name": "Data Analytics REST API",
    "version": "1.0.0",
    "description": "Аналитический API-сервис обработки данных (кейс E-soft)",
    "endpoints": {
        "POST /upload": "Загрузка файла CSV/Excel (лимит 25 МБ)",
        "GET /files": "Список загруженных файлов",
        "GET /data/stats?file_id=<id>": "Среднее, медиана и корреляция",
        "POST /data/clean?file_id=<id>": "Очистка данных (создаёт очищенную копию)",
        "GET /data/plot?file_id=<id>&plot=corr|hist|box": "PNG-график",
        "POST /analyze?file_id=<id>&plot=corr": "Полный анализ (статистика + график в БД)",
        "GET /data/file/<id>": "Скачать файл",
        "DELETE /data/file/<id>": "Удалить файл и связанные анализы"
    }
}


# --- Вспомогательные функции ------------------------------------------

def _db():
    """Возвращает свежую SessionLocal из конфигурации Flask."""
    session_cls = current_app.config.get("SESSION_FACTORY")
    assert session_cls is not None, "SESSION_FACTORY не задан в конфигурации"
    return session_cls()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_file_or_404(db, file_id: int) -> UploadedFileDB:
    record = db.query(UploadedFileDB).filter(UploadedFileDB.id == file_id).first()
    if not record:
        raise NotFoundError(f"Файл с ID {file_id} не найден в базе данных")
    return record


def _require_file_id(request) -> int:
    file_id = request.args.get("file_id", type=int)
    if not file_id:
        raise BadRequestError("Параметр query-строки file_id обязателен")
    return file_id


# --- Ресурс / -------------------------------------------------------

@analytics_bp.route("/", methods=["GET"])
def index():
    """Корневой эндпоинт: справка по доступным методам вместо 404."""
    return jsonify(SERVICE_INFO), 200


# --- CRUD: создание/чтение файлов -------------------------------------

@analytics_bp.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        raise BadRequestError("Файл не передан в теле запроса (ключ 'file')")

    file = request.files["file"]
    if file.filename == "":
        raise BadRequestError("Пустое имя файла")
    if not allowed_file(file.filename):
        raise UnsupportedMediaError(
            "Неподдерживаемый тип медиа. Разрешены только CSV и Excel (csv, xlsx, xls)"
        )

    limit = current_app.config["MAX_CONTENT_LENGTH"]
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > limit:
        raise BadRequestError(f"Файл слишком большой (макс. {limit} байт)")

    ext = file.filename.rsplit(".", 1)[1].lower()
    db = _db()
    try:
        binary_data = file.read()
        new_file = UploadedFileDB(
            filename=file.filename,
            file_ext=ext,
            file_size=len(binary_data),
            file_data=binary_data,
        )
        db.add(new_file)
        db.commit()
        db.refresh(new_file)
        return jsonify({
            "message": "Файл успешно загружен и сохранён в PostgreSQL",
            "file_id": new_file.id,
        }), 201
    except Exception as e:
        db.rollback()
        raise ProcessingError(f"Внутренняя ошибка сервера при сохранении: {str(e)}")
    finally:
        db.close()


@analytics_bp.route("/files", methods=["GET"])
def list_files():
    db = _db()
    try:
        records = db.query(UploadedFileDB).order_by(UploadedFileDB.id.desc()).all()
        files = [{
            "id": f.id,
            "filename": f.filename,
            "extension": f.file_ext,
            "size_bytes": f.file_size,
            "size_kb": round(f.file_size / 1024, 2),
            "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
            "is_clean_copy": f.original_file_id is not None,
        } for f in records]
        return jsonify({"count": len(files), "files": files}), 200
    finally:
        db.close()


@analytics_bp.route("/data/file/<int:file_id>", methods=["GET"])
def get_file(file_id: int):
    db = _db()
    try:
        record = _get_file_or_404(db, file_id)
        return send_file(
            __import__("io").BytesIO(record.file_data),
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=record.filename,
        )
    finally:
        db.close()


@analytics_bp.route("/data/file/<int:file_id>", methods=["DELETE"])
def delete_file(file_id: int):
    db = _db()
    try:
        record = _get_file_or_404(db, file_id)
        db.delete(record)  # cascade "delete-orphan" удалит связанные анализы
        db.commit()
        return jsonify({
            "message": f"Файл {file_id} удалён вместе с его анализами",
            "file_id": file_id,
        }), 200
    finally:
        db.close()


# --- Анализ -------------------------------------------------------------

@analytics_bp.route("/data/stats", methods=["GET"])
def get_stats():
    file_id = _require_file_id(request)
    db = _db()
    try:
        record = _get_file_or_404(db, file_id)
        df = services.load_file_to_df(record.file_data, record.file_ext)
        stats = services.compute_stats(df)
        return jsonify({
            "file_id": file_id,
            "filename": record.filename,
            "analytics": stats,
        }), 200
    finally:
        db.close()


@analytics_bp.route("/data/clean", methods=["POST"])
def clean_data():
    file_id = _require_file_id(request)
    db = _db()
    try:
        record = _get_file_or_404(db, file_id)
        df = services.load_file_to_df(record.file_data, record.file_ext)
        clean_df, metrics = services.clean_dataframe(df)
        new_bytes = services.dataframe_to_bytes(clean_df, record.file_ext)

        clean_copy = UploadedFileDB(
            filename=f"clean_{record.filename}",
            file_ext=record.file_ext,
            file_size=len(new_bytes),
            original_file_id=record.id,
            file_data=new_bytes,
        )
        db.add(clean_copy)
        db.commit()
        db.refresh(clean_copy)

        return jsonify({
            "status": "Очистка успешно завершена",
            "original_file_id": file_id,
            "cleaned_file_id": clean_copy.id,
            "metrics": metrics,
        }), 201
    except Exception as e:
        db.rollback()
        if isinstance(e, APIError):
            raise
        raise ProcessingError(f"Ошибка в ходе очистки: {str(e)}")
    finally:
        db.close()


@analytics_bp.route("/analyze", methods=["POST"])
def analyze():
    file_id = _require_file_id(request)
    plot_type = request.args.get("plot", "corr")
    if plot_type not in ALLOWED_PLOT_TYPES:
        raise BadRequestError(f"Неизвестный тип графика. Доступно: {sorted(ALLOWED_PLOT_TYPES)}")

    db = _db()
    try:
        record = _get_file_or_404(db, file_id)
        df = services.load_file_to_df(record.file_data, record.file_ext)
        stats = services.compute_stats(df)
        plot_bytes = services.build_plot(df, plot_type)

        result = AnalysisResultDB(
            file_id=file_id,
            mean_values=stats["mean"],
            median_values=stats["median"],
            correlation_matrix=stats["correlation"],
            plot_data=plot_bytes,
        )
        db.add(result)
        db.commit()
        db.refresh(result)

        return jsonify({
            "message": "Анализ сохранён",
            "analysis_id": result.id,
            "file_id": file_id,
            "plot_type": plot_type,
        }), 201
    except Exception as e:
        db.rollback()
        if isinstance(e, APIError):
            raise
        raise ProcessingError(f"Ошибка обработки данных Pandas: {str(e)}")
    finally:
        db.close()


# --- График ---------------------------------------------------------------

@analytics_bp.route("/data/plot", methods=["GET"])
def get_plot():
    file_id = _require_file_id(request)
    plot_type = request.args.get("plot", "corr")
    if plot_type not in ALLOWED_PLOT_TYPES:
        raise BadRequestError(f"Неизвестный тип графика. Доступно: {sorted(ALLOWED_PLOT_TYPES)}")

    db = _db()
    try:
        record = _get_file_or_404(db, file_id)
        df = services.load_file_to_df(record.file_data, record.file_ext)
        plot_bytes = services.build_plot(df, plot_type)

        result = AnalysisResultDB(file_id=file_id, plot_data=plot_bytes)
        db.add(result)
        db.commit()
        db.refresh(result)

        return send_file(
            __import__("io").BytesIO(plot_bytes),
            mimetype="image/png",
            as_attachment=False,
            download_name=f"plot_{file_id}.png",
        ), 200
    except Exception as e:
        db.rollback()
        if isinstance(e, APIError):
            raise
        raise ProcessingError(f"Ошибка визуализации: {str(e)}")
    finally:
        db.close()


# --- Обработчик ошибок blueprint -----------------------------------------

@analytics_bp.errorhandler(APIError)
def handle_api_error(err: APIError):
    return jsonify({"error": err.message}), err.status_code