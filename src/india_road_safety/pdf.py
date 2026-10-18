"""PDF text extraction (shared by collectors).

Kept dependency-light: uses ``pypdf`` when available. Extraction is best-effort;
callers must treat unparsable values as ``None`` rather than guessing.
"""

from __future__ import annotations

from io import BytesIO
from typing import Optional


def extract_text(pdf_bytes: bytes, max_pages: Optional[int] = None) -> str:
    """Return concatenated per-page text from a PDF, separated by a page marker."""
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - dependency guard
        return ""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception:  # pragma: no cover - defensive
        return ""
    parts: list[str] = []
    for i, page in enumerate(reader.pages):
        if max_pages is not None and i >= max_pages:
            break
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # pragma: no cover - defensive
            continue
    return "\n<<<PAGE>>>\n".join(parts)
