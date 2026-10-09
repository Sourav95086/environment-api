from pathlib import Path
from pypdf import PdfReader

def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"[Page {page_number}]\n{text}")
    extracted = "\n\n".join(pages).strip()
    if not extracted:
        raise ValueError(
            f"No extractable text found in {path.name}. "
            "This may be a scanned PDF; OCR support is not included in this starter."
        )
    return extracted
