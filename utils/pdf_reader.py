# =============================================
# utils/pdf_reader.py
# =============================================
from PyPDF2 import PdfReader


def read_pdf(file_path: str) -> str:
    """Read PDF and return text."""
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text