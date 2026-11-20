"""Capture real screenshots of the running app (needs: pip install playwright + Google Chrome; app on $URL)."""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = os.getenv("URL", "http://127.0.0.1:7861")
OUT = Path(__file__).resolve().parents[1] / "artifacts" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def ask(page, text, wait_ms=60000):
    box = page.get_by_placeholder("Ask a question about the selected course…")
    box.fill(text)
    box.press("Enter")
    page.wait_for_function("() => !document.body.innerText.includes('Retrieving evidence')", timeout=wait_ms)
    page.wait_for_timeout(1500)


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 1360, "height": 900}, device_scale_factor=2)
    pg.goto(URL); pg.wait_for_timeout(3000)
    pg.screenshot(path=OUT / "01_course_library.png", full_page=True)
    pg.get_by_role("tab", name="Ask").click()
    ask(pg, "What is the difference between population variance and sample variance?") if False else None
    pg.get_by_label("Selected course").click(); pg.get_by_role("option", name="Statistics").click()
    ask(pg, "What is the difference between population variance and sample variance?")
    pg.screenshot(path=OUT / "02_grounded_qa_evidence_trail.png", full_page=True)
    pg.get_by_label("Open a citation (source viewer)").click()
    pg.get_by_role("option").first.click(); pg.wait_for_timeout(800)
    pg.screenshot(path=OUT / "03_citation_source_viewer.png", full_page=True)
    pg.get_by_label("Selected course").click(); pg.get_by_role("option", name="Python").click()
    ask(pg, "What is the average salary of a Python engineer in Egypt?")
    pg.screenshot(path=OUT / "04_abstention.png", full_page=True)
    pg.get_by_role("tab", name="Retrieval Inspector").click()
    pg.get_by_label("Query").fill("zip stops at the shortest input"); pg.get_by_role("button", name="Retrieve").click(); pg.wait_for_timeout(2500)
    pg.screenshot(path=OUT / "05_retrieval_inspector.png", full_page=True)
    pg.get_by_role("tab", name="Documents").click(); pg.wait_for_timeout(1000)
    pg.screenshot(path=OUT / "06_documents.png", full_page=True)
    pg.get_by_role("tab", name="Dashboard").click(); pg.wait_for_timeout(2000)
    pg.screenshot(path=OUT / "07_dashboard.png", full_page=True)
    pg.get_by_role("tab", name="Evaluation").click(); pg.get_by_role("button", name="Load results").click(); pg.wait_for_timeout(1500)
    pg.screenshot(path=OUT / "08_evaluation.png", full_page=True)
    m = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True)
    m.goto(URL); m.wait_for_timeout(3000)
    m.screenshot(path=OUT / "09_mobile.png", full_page=True)
    b.close()
print("ok")
