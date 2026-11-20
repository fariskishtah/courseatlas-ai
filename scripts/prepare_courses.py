"""Generate the original demo course packs (PDF, DOCX, CSV, TXT) for three courses.

Usage: python scripts/prepare_courses.py
Output: data/sample_courses/<course_id>/*  and data/manifests/sources.json
"""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
import course_content as C  # noqa: E402

OUT = ROOT / "data" / "sample_courses"


def make_pdf(path: Path, title: str, sections, course_name: str) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Preformatted
    from xml.sax.saxutils import escape

    styles = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=styles["BodyText"], fontSize=10.5, leading=15, spaceAfter=8)
    code = ParagraphStyle("c", parent=styles["Code"], fontSize=9, leading=12, leftIndent=12)

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(2 * cm, 28.2 * cm, f"CourseAtlas Demo Course Pack | {course_name}")
        canvas.drawRightString(19 * cm, 1.2 * cm, f"Page {doc.page}")
        canvas.drawString(2 * cm, 1.2 * cm, "Original educational material, CC BY 4.0")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, title=title, author="CourseAtlas AI demo",
                            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2.4 * cm, bottomMargin=2 * cm)
    flow = [Paragraph(title, styles["Title"]), Paragraph(f"{course_name} - independently written demonstration notes. "
            "Not official university material.", body), PageBreak()]
    for i, (heading, text) in enumerate(sections):
        flow.append(Paragraph(escape(heading), styles["Heading1"]))
        for para in text.split("\n\n"):
            if para.startswith("class ") or "\n    " in para:
                flow.append(Preformatted(para, code))
            else:
                flow.append(Paragraph(escape(para).replace("\n", "<br/>"), body))
        if i < len(sections) - 1:
            flow.append(PageBreak())
    doc.build(flow, onFirstPage=header_footer, onLaterPages=header_footer)


def make_docx(path: Path, title: str, sections, tables) -> None:
    from docx import Document
    d = Document()
    d.core_properties.title = title
    d.add_heading(title, 0)
    d.add_paragraph("Independently written demonstration material (CC BY 4.0). Not official university material.")
    for heading, text in sections:
        d.add_heading(heading, 1)
        for para in text.split("\n\n"):
            d.add_paragraph(para)
    for t_title, header, rows in tables:
        d.add_heading(t_title, 1)
        t = d.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"
        for i, h in enumerate(header):
            t.rows[0].cells[i].text = h
        for r in rows:
            cells = t.add_row().cells
            for i, v in enumerate(r):
                cells[i].text = str(v)
    d.save(path)


def write_csv(path: Path, header, rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])


def stats_rows():
    """Worked examples whose values are computed here, never typed by hand."""
    datasets = {
        "A": [2, 4, 4, 4, 5, 5, 7, 9],
        "B": [10, 12, 23, 23, 16, 23, 21, 16],
        "C": [1, 2, 3, 4, 5, 6, 7, 8, 9, 100],
    }
    rows, n = [], 1
    for key, data in datasets.items():
        label = ",".join(map(str, data))
        stats = [
            ("Mean", statistics.mean(data), "sum divided by n"),
            ("Median", statistics.median(data), "middle value of sorted data"),
            ("Population variance", statistics.pvariance(data), "divide squared deviations by N"),
            ("Sample variance", statistics.variance(data), "divide squared deviations by n - 1"),
            ("Population standard deviation", statistics.pstdev(data), "square root of population variance"),
            ("Sample standard deviation", statistics.stdev(data), "square root of sample variance"),
        ]
        for name, val, note in stats:
            rows.append([f"ST{n:03d}", "Descriptive statistics", f"Dataset {key}: {label}", len(data), name, round(val, 4), note])
            n += 1
    # probability examples
    prob = [
        ("Probability", "Fair die: P(rolling a 6)", 1, "P = 1/6", round(1 / 6, 4), "equally likely outcomes"),
        ("Probability", "Two fair coins: P(two heads)", 2, "P = 1/2 * 1/2", 0.25, "independent events"),
        ("Probability", "Two cards without replacement: P(both aces)", 2, "P = 4/52 * 3/51", round(4 / 52 * 3 / 51, 4), "conditional probability"),
        ("Bayes", "Disease 1%, sensitivity 95%, false positive 5%: P(disease | positive)", 1, "Bayes theorem", round(0.95 * 0.01 / (0.95 * 0.01 + 0.05 * 0.99), 4), "base rate effect"),
        ("Binomial", "10 fair coin flips: P(exactly 5 heads)", 10, "C(10,5) * 0.5^10", round(252 / 1024, 4), "binomial PMF"),
        ("Normal", "z-score of x = 85 with mean 70 and standard deviation 10", 1, "z = (x - mu) / sigma", 1.5, "standardization"),
        ("Confidence interval", "n = 36, mean 12.4, sigma 3: half-width of 95% CI", 36, "1.96 * sigma / sqrt(n)", round(1.96 * 3 / 6, 4), "margin of error"),
    ]
    for topic, ds, size, stat, val, note in prob:
        rows.append([f"ST{n:03d}", topic, ds, size, stat, val, note])
        n += 1
    return rows


def main() -> None:
    manifest = []
    specs = {
        "python": (C.PYTHON_PDF, C.PYTHON_DOCX, C.PYTHON_TXT, "python_practice_exercises.csv",
                   C.PYTHON_CSV_HEADER, C.PYTHON_CSV_ROWS),
        "statistics": (C.STATS_PDF, C.STATS_DOCX, C.STATS_TXT, "statistics_worked_examples.csv",
                       ["example_id", "topic", "dataset_or_scenario", "n", "statistic", "value", "method_note"], stats_rows()),
        "ml": (C.ML_PDF, C.ML_DOCX, C.ML_TXT, "ml_model_evaluation_runs.csv", C.ML_CSV_HEADER, None),
    }
    # ML f1 computed from precision/recall
    ml_rows = []
    for r in C.ML_CSV_ROWS:
        p, rc = r[5], r[6]
        r = list(r)
        r[7] = round(2 * p * rc / (p + rc), 4) if (p + rc) else 0.0
        ml_rows.append(r)
    prefix = {"python": "python", "statistics": "statistics", "ml": "ml"}
    for cid, (pdf, docx, txt, csv_name, header, rows) in specs.items():
        d = OUT / cid
        d.mkdir(parents=True, exist_ok=True)
        cname = C.COURSES[cid]["name"]
        make_pdf(d / f"{prefix[cid]}_lecture_notes.pdf", pdf[0], pdf[1], cname)
        make_docx(d / f"{prefix[cid]}_exercise_guide.docx", docx[0], docx[1], docx[2])
        (d / f"{prefix[cid]}_reference_notes.txt").write_text(txt, encoding="utf-8")
        write_csv(d / csv_name, header, rows if rows is not None else ml_rows)
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            manifest.append({
                "course_id": p.parent.name, "filename": p.name,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size,
                "source": "Original content written for CourseAtlas AI (scripts/course_content.py)",
                "license": "CC BY 4.0",
            })
    (ROOT / "data" / "manifests").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "manifests" / "courses.json").write_text(json.dumps(C.COURSES, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "data" / "manifests" / "sources.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(manifest)} files")


if __name__ == "__main__":
    main()
