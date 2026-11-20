"""Upload validation: extension, real file type, size, zip-bomb guard, filename sanitisation. Nothing is executed."""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from ..config import get_config, path as cfg_path


class UploadError(ValueError):
    pass


_SAFE = re.compile(r"[^A-Za-z0-9._ \-()]")


def sanitize_filename(name: str) -> str:
    base = Path(str(name).replace("\\", "/")).name          # drops any directory / traversal components
    base = _SAFE.sub("_", base).strip(" .")
    if not base or base.startswith("."):
        raise UploadError("Unsafe or empty filename")
    stem, dot, ext = base.rpartition(".")
    if len(base) > 100:
        base = stem[: 95 - len(ext)] + "." + ext
    return base


def validate_upload(src: Path, original_name: str) -> str:
    cfg = get_config()["app"]
    name = sanitize_filename(original_name)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in cfg["allowed_extensions"]:
        raise UploadError(f"Unsupported type .{ext}. Allowed: {', '.join(cfg['allowed_extensions'])}")
    size = src.stat().st_size
    if size == 0:
        raise UploadError("File is empty")
    if size > cfg["max_upload_mb"] * 1024 * 1024:
        raise UploadError(f"File exceeds {cfg['max_upload_mb']} MB limit")
    head = src.read_bytes()[:8]
    if ext == "pdf" and not head.startswith(b"%PDF-"):
        raise UploadError("File content is not a PDF")
    if ext == "docx":
        if not zipfile.is_zipfile(src):
            raise UploadError("File content is not a DOCX")
        with zipfile.ZipFile(src) as z:
            names = z.namelist()
            if "word/document.xml" not in names:
                raise UploadError("File content is not a DOCX")
            if sum(i.file_size for i in z.infolist()) > 200 * 1024 * 1024:
                raise UploadError("DOCX expands to an unreasonable size")
            if any("vbaProject" in n for n in names):
                raise UploadError("Macro-enabled documents are rejected")
    if ext in ("csv", "txt"):
        raw = src.read_bytes()
        if b"\x00" in raw[:100_000]:
            raise UploadError("Binary data found in a text file")
    return name


def store_upload(src: Path, original_name: str, course_id: str) -> tuple[Path, str]:
    name = validate_upload(src, original_name)
    if not re.fullmatch(r"[a-z0-9_\-]+", course_id):
        raise UploadError("Invalid course")
    dest_dir = cfg_path("upload_dir") / course_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = (dest_dir / name).resolve()
    if dest_dir.resolve() not in dest.parents:
        raise UploadError("Path traversal blocked")
    shutil.copyfile(src, dest)
    return dest, name
