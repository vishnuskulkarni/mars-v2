import os
from typing import List, Tuple


async def save_upload_files(files, session_dir: str) -> Tuple[List[str], List[str]]:
    """Save uploaded files to session directory. Returns (literature_files, data_files)."""
    os.makedirs(session_dir, exist_ok=True)
    literature_files = []
    data_files = []

    for file in files:
        file_path = os.path.join(session_dir, file.filename)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        ext = os.path.splitext(file.filename)[1].lower()
        if ext == ".pdf":
            literature_files.append(file_path)
        elif ext in (".csv", ".xlsx", ".xls"):
            data_files.append(file_path)

    return literature_files, data_files


def parse_all_pdfs(file_paths: List[str]) -> str:
    """Extract text from all PDF files."""
    from backend.utils.pdf_parser import extract_pdf_text

    all_text = []
    for path in file_paths:
        text = extract_pdf_text(path)
        filename = os.path.basename(path)
        all_text.append(f"=== {filename} ===\n{text}\n")
    return "\n".join(all_text) if all_text else "No literature files provided."


def parse_all_data_files(file_paths: List[str]) -> str:
    """Parse all data files and return summaries."""
    from backend.utils.data_parser import summarize_data_file

    all_summaries = []
    for path in file_paths:
        summary = summarize_data_file(path)
        filename = os.path.basename(path)
        all_summaries.append(f"=== {filename} ===\n{summary}\n")
    return "\n".join(all_summaries) if all_summaries else "No data files provided."
