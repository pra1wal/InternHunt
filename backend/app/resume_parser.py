from __future__ import annotations

from io import BytesIO
from zipfile import BadZipFile, ZipFile

from docx import Document
from pypdf import PdfReader

MAX_PDF_PAGES = 30
MAX_EXTRACTED_CHARS = 60000


def extract_resume_text(filename: str, file_data: bytes) -> str:
    name = filename.lower()

    if name.endswith(".pdf"):
        reader = PdfReader(BytesIO(file_data), strict=False)
        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f"PDFs may contain at most {MAX_PDF_PAGES} pages.")

        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        text = "\n".join(parts)

    elif name.endswith(".docx"):
        try:
            with ZipFile(BytesIO(file_data)) as archive:
                names = set(archive.namelist())
                if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                    raise ValueError("The uploaded file is not a valid DOCX document.")
        except BadZipFile as exc:
            raise ValueError("The uploaded file is not a valid DOCX document.") from exc

        document = Document(BytesIO(file_data))
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" ".join(cell.text for cell in row.cells))
        text = "\n".join(parts)

    else:
        raise ValueError("Only PDF and DOCX resumes are supported.")

    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return text[:MAX_EXTRACTED_CHARS]
