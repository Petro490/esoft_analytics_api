"""Сервисный слой: вся работа с Pandas/Matplotlib изолирована здесь.

Роуты (routes.py) только парсят HTTP-запрос и отдают ответ, а бизнес-логика
обработки данных живёт в этих функциях. Это делает логику тестируемой без
Flask и переиспользуемой между эндпоинтами.
"""
import io

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Фоновый (не-GUI) режим для Matplotlib
import matplotlib.pyplot as plt

from app.errors import EmptyNumericError, ProcessingError


# --- Работа с DataFrame ---------------------------------------------

def load_file_to_df(file_data: bytes, file_ext: str) -> pd.DataFrame:
    """Воссоздаёт DataFrame из байтов файла (CSV или Excel)."""
    try:
        if file_ext == "csv":
            return pd.read_csv(io.BytesIO(file_data))
        return pd.read_excel(io.BytesIO(file_data), engine="openpyxl")
    except Exception as e:  # невалидный/битый файл
        raise ProcessingError(f"Не удалось прочитать файл: {str(e)}")


def _numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    """Возвращает только числовые колонки или бросает EmptyNumericError."""
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.empty:
        raise EmptyNumericError()
    return numeric_df


def compute_stats(df: pd.DataFrame) -> dict:
    """Среднее, медиана и корреляционная матрица для числовых колонок.

    Возвращает обычные питон-dict (конвертация из numpy), пригодные для JSON.
    """
    numeric_df = _numeric_df(df)
    return {
        "mean": numeric_df.mean().round(4).to_dict(),
        "median": numeric_df.median().round(4).to_dict(),
        "correlation": numeric_df.corr().round(4).to_dict(),
    }


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Очистка: remove duplicates + fill NaN. Возвращает (df, метрики)."""
    initial_rows = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    removed = initial_rows - len(df)

    filled_columns = []
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            if df[col].isna().any():
                df[col] = df[col].fillna(df[col].mean())
                filled_columns.append(col)
        else:
            if df[col].isna().any():
                df[col] = df[col].fillna("Unknown")
                filled_columns.append(col)

    # Оставляем исходные имена колонок (после reset_index drop индекс исчезает)
    df.columns = [str(c) for c in df.columns]

    metrics = {
        "removed_duplicates_count": removed,
        "current_rows_count": len(df),
        "filled_columns": filled_columns,
    }
    return df, metrics


def dataframe_to_bytes(df: pd.DataFrame, file_ext: str) -> bytes:
    """Сериализует DataFrame обратно в байты (CSV или Excel)."""
    output = io.BytesIO()
    if file_ext == "csv":
        df.to_csv(output, index=False)
    else:
        df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()


# --- Визуализация ----------------------------------------------------

def build_plot(df: pd.DataFrame, plot_type: str = "corr") -> bytes:
    """Строит график и возвращает PNG в байтах.

    plot_type:
      - "corr" — тепловая карта корреляции
      - "hist"  — гистограммы распределения числовых колонок
      - "box"   — ящики с усами (разброс значений)
    """
    numeric_df = _numeric_df(df)

    try:
        if plot_type == "hist":
            fig, axes = plt.subplots(nrows=max(1, len(numeric_df.columns)), figsize=(8, 2.5 * len(numeric_df.columns)))
            if len(numeric_df.columns) == 1:
                axes = [axes]
            for ax, col in zip(axes, numeric_df.columns):
                numeric_df[col].hist(ax=ax, bins=20)
                ax.set_title(str(col))
            fig.tight_layout()
        elif plot_type == "box":
            fig, ax = plt.subplots(figsize=(8, 6))
            numeric_df.boxplot(ax=ax, rot=45)
            ax.set_title("Ящики с усами (разброс значений)")
            fig.tight_layout()
        else:  # "corr" — по умолчанию
            fig, ax = plt.subplots(figsize=(8, 6))
            im = ax.imshow(numeric_df.corr(), cmap="coolwarm", aspect="auto")
            ax.set_xticks(range(len(numeric_df.columns)))
            ax.set_yticks(range(len(numeric_df.columns)))
            ax.set_xticklabels(numeric_df.columns, rotation=45)
            ax.set_yticklabels(numeric_df.columns)
            plt.colorbar(im, ax=ax)
            ax.set_title("Матрица корреляции", y=1.05)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        raise ProcessingError(f"Ошибка визуализации: {str(e)}")