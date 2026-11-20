import pytest

from src.ingestion import IngestionError, extract
from src.ingestion import cleaning
from src.ingestion.chunking import chunk_blocks


def test_txt_line_references_and_sections(sample_files):
    d = extract(sample_files / "notes.txt")
    assert any(b.section == "FUNCTIONS" for b in d.blocks)
    b = next(b for b in d.blocks if "while loop" in b.text)
    assert b.line_start == 4 and b.line_end == 4


def test_csv_rows_keep_columns_and_ids(sample_files):
    d = extract(sample_files / "runs.csv")
    rows = [b for b in d.blocks if b.row]
    assert [b.row for b in rows] == [1, 2, 3]
    assert "model: forest; score: 0.95" in rows[1].text
    assert "score: (missing)" in rows[2].text            # missing values are explicit, not dropped
    assert d.blocks[0].row == 0 and "3 data rows" in d.blocks[0].text


def test_docx_headings_and_tables(sample_files):
    d = extract(sample_files / "guide.docx")
    assert d.page_count is None                           # no invented page numbers
    assert any("Bayes" in b.text and b.section == "Probability" for b in d.blocks)
    assert any("Dist: Binomial; Mean: n*p" in b.text for b in d.blocks)


def test_pdf_pages_and_header_footer_removal(sample_files):
    d = extract(sample_files / "lecture.pdf")
    assert d.page_count == 4
    text = " ".join(b.text for b in d.blocks)
    assert "REPEATED HEADER" not in text
    assert not any(b.text.strip() == "Page 2" for b in d.blocks)
    b = next(b for b in d.blocks if "Overfitting" in b.text)
    assert b.page == 2


def test_empty_and_corrupt_and_unsupported(tmp_path):
    (tmp_path / "e.txt").write_text("   \n")
    with pytest.raises(IngestionError):
        extract(tmp_path / "e.txt")
    (tmp_path / "bad.pdf").write_bytes(b"not a pdf at all")
    with pytest.raises(IngestionError):
        extract(tmp_path / "bad.pdf")
    (tmp_path / "bad.docx").write_bytes(b"PK garbage")
    with pytest.raises(IngestionError):
        extract(tmp_path / "bad.docx")
    (tmp_path / "x.exe").write_bytes(b"MZ")
    with pytest.raises(IngestionError):
        extract(tmp_path / "x.exe")
    (tmp_path / "m.csv").write_text("a,b\n1,2,3,4\n5,6\n")
    with pytest.raises(IngestionError):
        extract(tmp_path / "m.csv")
    (tmp_path / "empty.csv").write_text("")
    with pytest.raises(IngestionError):
        extract(tmp_path / "empty.csv")


def test_txt_latin1_fallback_and_binary_reject(tmp_path):
    (tmp_path / "l.txt").write_bytes("caf\xe9 au lait".encode("latin-1"))
    d = extract(tmp_path / "l.txt")
    assert "caf" in d.blocks[0].text and d.warnings
    (tmp_path / "b.txt").write_bytes(b"abc\x00def")
    with pytest.raises(IngestionError):
        extract(tmp_path / "b.txt")


def test_cleaning_preserves_code_math_and_units():
    t = "def f(x):\n    return x ** 2   \n\nValue: 9.81 m/s^2 and \u03c3 = 2.5\u200b"
    c = cleaning.clean_text(t)
    assert "    return x ** 2" in c and "9.81 m/s^2" in c and "\u200b" not in c


def test_cleaning_fixes_mojibake_and_wrapped_lines():
    assert cleaning.clean_text("it\u00e2\u20ac\u2122s") == "it's"
    assert cleaning.clean_text("a sentence that was\nwrapped by the layout") == "a sentence that was wrapped by the layout"


def test_duplicate_paragraphs_dropped():
    p = "This is a fairly long repeated paragraph that appears twice in the text."
    assert len(cleaning.drop_duplicate_paragraphs([p, "other", p])) == 2


def test_chunk_provenance_rows_atomic_and_stable_ids(sample_files):
    d = extract(sample_files / "runs.csv")
    kw = dict(course_id="c", doc_id="d1", doc_title="Runs", filename="runs.csv", file_type="csv", chunk_size=2000)
    a, b = chunk_blocks(d.blocks, **kw), chunk_blocks(d.blocks, **kw)
    assert len(a) == len(d.blocks)                      # one chunk per row even though they would fit together
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
    assert a[2].location == "Row 2" and a[2].row == 2 and a[2].content_hash


def test_chunks_never_cross_pages(sample_files):
    d = extract(sample_files / "lecture.pdf")
    ch = chunk_blocks(d.blocks, course_id="c", doc_id="d", doc_title="L", filename="lecture.pdf", file_type="pdf", chunk_size=5000)
    assert all(c.page for c in ch) and len({c.page for c in ch}) == 4
    assert all(c.location.startswith("Page") for c in ch)


def test_oversized_paragraph_split_on_sentences_and_code_kept():
    from src.models import Block
    long = " ".join(f"Sentence number {i} is here." for i in range(60))
    ch = chunk_blocks([Block(text=long, end=len(long))], course_id="c", doc_id="d", doc_title="T", filename="t.txt", file_type="docx", chunk_size=300, chunk_overlap=0)
    assert len(ch) > 3 and all(len(c.text) <= 330 for c in ch)
    code = "def f():\n    return 1\n    pass"
    ch = chunk_blocks([Block(text=code, end=len(code))], course_id="c", doc_id="d", doc_title="T", filename="t.txt", file_type="docx", chunk_size=10)
    assert len(ch) == 1 and ch[0].text == code
