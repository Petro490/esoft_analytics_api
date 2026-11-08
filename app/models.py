from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, LargeBinary, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


def utcnow() -> datetime:
    """Текущее время в UTC (timezone-aware) — современная замена datetime.utcnow()."""
    return datetime.now(timezone.utc)


class UploadedFileDB(Base):
    """Таблица для хранения исходных загруженных файлов."""
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_ext = Column(String(10), nullable=False)          # Расширение без точки
    file_size = Column(Integer, nullable=False)            # Размер в байтах
    original_file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=True)
    file_data = Column(LargeBinary, nullable=False)        # Хранение файла в байтах
    uploaded_at = Column(DateTime, default=utcnow)

    # Связь: у файла может быть "родитель" (исходник очищенной копии)
    parent = relationship("UploadedFileDB", remote_side=[id])
    analyses = relationship("AnalysisResultDB", back_populates="file", cascade="all, delete-orphan")


class AnalysisResultDB(Base):
    """Таблица для хранения вычисленной статистики по файлам + ссылка на график."""
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False, index=True)
    mean_values = Column(JSON, nullable=True)
    median_values = Column(JSON, nullable=True)
    correlation_matrix = Column(JSON, nullable=True)
    plot_data = Column(LargeBinary, nullable=True)         # PNG графика (опционально)
    calculated_at = Column(DateTime, default=utcnow)

    file = relationship("UploadedFileDB", back_populates="analyses")