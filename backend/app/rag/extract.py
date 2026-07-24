"""Extract plain text from uploaded documents (PDF and text formats)."""

from __future__ import annotations

import io

_TEXT_SUFFIXES = (".txt", ".md", ".markdown", ".csv", ".json")


class UnsupportedDocumentError(ValueError):
    """Raised when a document's type can't be parsed to text."""


def extract_text(filename: str, content_type: str | None, data: bytes) -> str:
    name = filename.lower()
    ctype = (content_type or "").lower()

    if name.endswith(".pdf") or ctype == "application/pdf":
        return _extract_pdf(data)
    if name.endswith(_TEXT_SUFFIXES) or ctype.startswith("text/"):
        return data.decode("utf-8", errors="replace")

    raise UnsupportedDocumentError(f"Unsupported document type for {filename!r} ({content_type})")


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader  # noqa: PLC0415 - lazy: only needed for PDFs

    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)
