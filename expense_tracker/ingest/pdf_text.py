from __future__ import annotations

import io
from dataclasses import dataclass

import pdfplumber


@dataclass
class PdfExtractResult:
    text: str
    line_count: int
    page_count: int
    low_confidence: bool


def extract_text_from_pdf(pdf_bytes: bytes) -> PdfExtractResult:
    lines: list[str] = []
    page_count = 0
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)
    combined = "\n".join(lines)
    low = len(lines) < 5
    return PdfExtractResult(
        text=combined,
        line_count=len(lines),
        page_count=page_count,
        low_confidence=low,
    )
