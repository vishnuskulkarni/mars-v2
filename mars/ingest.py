"""File ingestion: PDF text extraction and dataset summarisation.

Ported from backend/utils/{pdf_parser,data_parser}.py, kept self-contained so
the mars/ package has no dependency on the legacy backend/ app. PDF extraction
tries pypdf, then pdfplumber, then PyMuPDF — whichever is installed and works.
"""

from __future__ import annotations

import os
from typing import List, Optional

import pandas as pd


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
def extract_pdf_text(file_path: str) -> str:
    """Extract text from a PDF, trying multiple libraries in order."""
    # 1) pypdf (listed in the build spec's requirements).
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[Page {i + 1}]\n{text.strip()}")
        if pages:
            return "\n\n".join(pages)
    except Exception:
        pass

    # 2) pdfplumber.
    try:
        import pdfplumber

        pages = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text and text.strip():
                    pages.append(f"[Page {i + 1}]\n{text.strip()}")
        if pages:
            return "\n\n".join(pages)
    except Exception:
        pass

    # 3) PyMuPDF.
    try:
        import fitz

        doc = fitz.open(file_path)
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                pages.append(f"[Page {i + 1}]\n{text.strip()}")
        doc.close()
        if pages:
            return "\n\n".join(pages)
    except Exception:
        pass

    return "[Could not extract text from this PDF]"


def parse_all_pdfs(file_paths: List[str]) -> str:
    """Concatenate extracted text from every PDF, labelled by filename."""
    chunks = []
    for path in file_paths:
        text = extract_pdf_text(path)
        chunks.append(f"=== {os.path.basename(path)} ===\n{text}\n")
    return "\n".join(chunks) if chunks else "No literature files provided."


# --------------------------------------------------------------------------- #
# Datasets
# --------------------------------------------------------------------------- #
def load_dataframe(file_path: str) -> Optional[pd.DataFrame]:
    """Load a CSV/Excel file into a DataFrame, or None if unsupported/unreadable.

    CSVs are read with delimiter auto-detection (comma/semicolon/tab/pipe), since
    real-world exports vary (e.g. the UCI student datasets use ';')."""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".csv":
            # sep=None + python engine sniffs the delimiter. Fall back to comma.
            try:
                df = pd.read_csv(file_path, sep=None, engine="python")
                if df.shape[1] == 1:  # sniffer missed a non-comma delimiter
                    raise ValueError("single column")
                return df
            except Exception:
                return pd.read_csv(file_path)
        if ext in (".xlsx", ".xls"):
            return pd.read_excel(file_path)
    except Exception:
        return None
    return None


def load_first_dataframe(file_paths: List[str]) -> Optional[pd.DataFrame]:
    """Return the first data file that loads successfully (used for plotting/gates)."""
    for path in file_paths:
        df = load_dataframe(path)
        if df is not None:
            return df
    return None


def schema_brief(df: pd.DataFrame, max_cols: int = 60) -> str:
    """Compact schema for the data agent's planning call: columns, dtypes,
    non-null counts, and a couple of sample values per column."""
    if df is None:
        return "No dataset available."
    lines = [f"rows={df.shape[0]}, columns={df.shape[1]}", "columns:"]
    for col in list(df.columns)[:max_cols]:
        s = df[col]
        nonnull = int(s.notna().sum())
        sample = [str(v) for v in s.dropna().unique()[:3]]
        lines.append(f"  - {col} ({s.dtype}, non-null {nonnull}/{len(df)}) e.g. {', '.join(sample)}")
    if df.shape[1] > max_cols:
        lines.append(f"  ... and {df.shape[1] - max_cols} more columns")
    return "\n".join(lines)


def summarize_data_file(file_path: str) -> str:
    """Produce a statistical text summary of one CSV/Excel file."""
    df = load_dataframe(file_path)
    if df is None:
        return f"[Error parsing data file: {os.path.basename(file_path)}]"

    parts = [
        f"Shape: {df.shape[0]} rows x {df.shape[1]} columns",
        f"\nColumn types:\n{df.dtypes.to_string()}",
        f"\nDescriptive statistics:\n{df.describe(include='all').to_string()}",
        f"\nMissing values:\n{df.isnull().sum().to_string()}",
    ]
    numeric_cols = df.select_dtypes(include="number")
    if len(numeric_cols.columns) >= 2:
        parts.append(f"\nCorrelation matrix:\n{numeric_cols.corr().to_string()}")
    parts.append(f"\nFirst 5 rows:\n{df.head().to_string()}")
    return "\n".join(parts)


def parse_all_data_files(file_paths: List[str]) -> str:
    """Concatenate summaries for every data file, labelled by filename."""
    summaries = []
    for path in file_paths:
        summaries.append(f"=== {os.path.basename(path)} ===\n{summarize_data_file(path)}\n")
    return "\n".join(summaries) if summaries else "No data files provided."
