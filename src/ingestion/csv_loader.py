"""CSV extraction. Each data row becomes one atomic block that keeps column names; row ids are preserved."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..models import Block, ExtractedDoc
from .common import IngestionError, finalize

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def _check_rectangular(path: Path, enc: str) -> None:
    """pandas silently turns extra leading fields into an index; reject ragged rows explicitly."""
    import csv
    with open(path, newline="", encoding=enc) as f:
        rows = csv.reader(f)
        header = next(rows, None)
        if header is None:
            raise IngestionError("CSV has no data rows")
        for n, r in enumerate(rows, start=2):
            if r and len(r) != len(header):
                raise IngestionError(f"Malformed CSV: line {n} has {len(r)} fields, expected {len(header)}")


def read_csv(path: Path) -> tuple[pd.DataFrame, str]:
    last = None
    for enc in ENCODINGS:
        try:
            _check_rectangular(path, enc)
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding=enc, on_bad_lines="error")
            return df, enc
        except UnicodeDecodeError as e:
            last = e
        except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
            raise IngestionError(f"Malformed CSV: {e}") from e
    raise IngestionError(f"Unsupported encoding: {last}")


def load_csv(path: Path) -> ExtractedDoc:
    df, enc = read_csv(path)
    if df.empty or len(df.columns) == 0:
        raise IngestionError("CSV has no data rows")
    cols = [str(c).strip() for c in df.columns]
    blocks = [Block(text=f"Schema of {path.name}: {len(df)} data rows with columns {', '.join(cols)}.",
                    kind="row", row=0, section="Header")]
    warnings = []
    for i, rec in enumerate(df.itertuples(index=False), start=1):
        parts = []
        for c, v in zip(cols, rec):
            v = str(v).strip()
            parts.append(f"{c}: {v if v else '(missing)'}")
        blocks.append(Block(text=f"Row {i} - " + "; ".join(parts), kind="row", row=i, section=f"Row {i}"))
    if (df == "").any().any():
        warnings.append("Some cells are empty; they are kept as '(missing)'.")
    return ExtractedDoc(blocks=finalize(blocks), method=f"pandas.read_csv (encoding={enc})", page_count=None, warnings=warnings)
