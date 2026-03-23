def extract_pdf_text(file_path: str) -> str:
    """Extract text from a PDF file using PyMuPDF, falling back to pdfplumber."""
    try:
        import fitz  # PyMuPDF

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

    # Fallback to pdfplumber
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

    return "[Could not extract text from this PDF]"
