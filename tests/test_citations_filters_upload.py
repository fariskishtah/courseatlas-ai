import zipfile

import pytest

from src.citations.provenance import build_sources, citation_label
from src.citations.validator import validate_citations
from src.retrieval.filters import InvalidQuestion, resolve_scope, validate_question
from src.utils import upload as U


def test_validator_removes_invented_ids():
    v = validate_citations("Fact one [S1]. Fact two [S9]. Both [S1, S2].", {"S1", "S2"})
    assert v["used"] == ["S1", "S2"] and v["invalid"] == ["S9"] and "[S9]" not in v["text"]
    assert not validate_citations("No tags here.", {"S1"})["has_valid"]


def test_label_from_metadata():
    assert citation_label({"doc_title": "ML Guide", "location": "Page 8"}) == "[ML Guide \u2014 Page 8]"


def test_context_is_bounded():
    from src.retrieval.retriever import Hit
    hits = [Hit(i, f"c{i}", 0.5, "x" * 400, {"doc_title": "D", "location": "L"}) for i in range(1, 10)]
    assert len(build_sources(hits, 1000)) == 2 and build_sources(hits, 1000)[1].sid == "S2"


def test_question_validation():
    assert validate_question("  hi\x00 ") == "hi"
    for bad in ("", "   ", None, "x" * 1001):
        with pytest.raises(InvalidQuestion):
            validate_question(bad)


def test_scope_resolution_is_explicit():
    known = {"python", "ml"}
    assert resolve_scope("python", known) == ["python"]
    with pytest.raises(InvalidQuestion):
        resolve_scope(["python", "ml"], known)            # multi-course must be enabled explicitly
    assert resolve_scope(["python", "ml"], known, allow_multi=True) == ["python", "ml"]
    for bad in (None, "", "nope"):
        with pytest.raises(InvalidQuestion):
            resolve_scope(bad, known)


def test_filename_sanitisation_blocks_traversal():
    assert U.sanitize_filename("../../etc/passwd.txt") == "passwd.txt"
    assert U.sanitize_filename("C:\\x\\..\\evil.csv") == "evil.csv"
    with pytest.raises(U.UploadError):
        U.sanitize_filename("..")
    assert "/" not in U.sanitize_filename("a/b/c<>|.txt")


def test_upload_rejections(tmp_path):
    def mk(name, data):
        p = tmp_path / "src" / name
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(data)
        return p
    with pytest.raises(U.UploadError):
        U.validate_upload(mk("a.exe", b"MZ"), "a.exe")
    with pytest.raises(U.UploadError):
        U.validate_upload(mk("a.txt", b""), "a.txt")
    with pytest.raises(U.UploadError):
        U.validate_upload(mk("fake.pdf", b"hello"), "fake.pdf")
    with pytest.raises(U.UploadError):
        U.validate_upload(mk("fake.docx", b"hello"), "fake.docx")
    with pytest.raises(U.UploadError):
        U.validate_upload(mk("bin.txt", b"a\x00b"), "bin.txt")
    big = mk("big.txt", b"a" * (11 * 1024 * 1024))
    with pytest.raises(U.UploadError):
        U.validate_upload(big, "big.txt")
    macro = tmp_path / "src" / "m.docx"
    with zipfile.ZipFile(macro, "w") as z:
        z.writestr("word/document.xml", "<x/>")
        z.writestr("word/vbaProject.bin", "x")
    with pytest.raises(U.UploadError):
        U.validate_upload(macro, "m.docx")
    ok = mk("ok.csv", b"a,b\n1,2\n")
    assert U.validate_upload(ok, "ok.csv") == "ok.csv"


def test_store_upload_stays_inside_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "cfg_path", lambda k: tmp_path / "uploads")
    src = tmp_path / "s.txt"
    src.write_text("hello")
    dest, name = U.store_upload(src, "../../evil.txt", "python")
    assert dest.parent == (tmp_path / "uploads" / "python").resolve() and name == "evil.txt"
    with pytest.raises(U.UploadError):
        U.store_upload(src, "x.txt", "../python")
