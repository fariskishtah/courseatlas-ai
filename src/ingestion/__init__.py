from __future__ import annotations

from pathlib import Path

from ..models import ExtractedDoc
from .common import IngestionError
from .csv_loader import load_csv
from .docx_loader import load_docx
from .pdf_loader import load_pdf
from .txt_loader import load_txt

LOADERS = {"pdf": load_pdf, "docx": load_docx, "csv": load_csv, "txt": load_txt}


def extract(path: Path) -> ExtractedDoc:
    ext = path.suffix.lower().lstrip(".")
    if ext not in LOADERS:
        raise IngestionError(f"Unsupported file type: .{ext}")
    return LOADERS[ext](path)
