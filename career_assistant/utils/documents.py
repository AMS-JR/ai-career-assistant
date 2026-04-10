# =============================================
# career_assistant.utils.documents - extract plain text from resume files
# =============================================

import subprocess
from pathlib import Path

from pypdf import PdfReader


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def _read_docx(path: Path) -> str:
    import docx

    document = docx.Document(str(path))
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def _read_doc(path: Path) -> str:
    """Legacy Word .doc: try antiword if installed (e.g. brew install antiword)."""
    try:
        result = subprocess.run(
            ["antiword", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError as e:
        raise ValueError(
            "Legacy .doc needs the `antiword` tool, or convert the file to .docx or .pdf."
        ) from e
    if result.returncode != 0:
        raise ValueError(
            "Could not read .doc (antiword failed). Convert to .docx or .pdf and try again."
        )
    return result.stdout or ""


def extract_resume_text(file_path: str) -> str:
    """
    Extract plain text from a resume file.

    Supports: .pdf, .docx, .doc (if `antiword` is on PATH).
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {file_path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    if suffix == ".doc":
        return _read_doc(path)
    raise ValueError(f"Unsupported file type: {suffix}. Use .pdf, .docx, or .doc.")
