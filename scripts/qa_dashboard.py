"""Browser smoke test against an already-running local ClearPath server."""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "submission" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1100}, device_scale_factor=1)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="networkidle")
        expect(page.locator("#run-checks")).to_be_disabled()
        page.screenshot(path=str(output / "01-workspace.png"), full_page=True)
        page.locator("#create-draft").click()
        expect(page.locator("#revision-badge")).to_have_text("Revision 1", timeout=120000)
        expect(page.locator("#run-checks")).to_be_disabled()
        page.locator("#approve-draft").click()
        expect(page.locator("#run-checks")).to_be_enabled()
        page.locator("#run-checks").click()
        expect(page.locator("#findings")).to_contain_text("Medication conflict detected")
        expect(page.locator("#findings")).to_contain_text("2 item discrepancies")
        expect(page.locator("#run-checks")).to_be_enabled()
        page.screenshot(path=str(output / "02-review-findings.png"), full_page=True)
        with page.expect_download() as download:
            page.locator("#download-report").click()
        report = Path(download.value.path()).read_text(encoding="utf-8")
        assert "PT-402" in report and "Amoxicillin" in report
        workflow_id = page.evaluate("localStorage.getItem('clearpath.workflow')")
        page.reload(wait_until="networkidle")
        expect(page.locator("#findings")).to_contain_text("Medication conflict detected")
        assert page.evaluate("localStorage.getItem('clearpath.workflow')") == workflow_id
        page.locator("#review-note").fill("Updated note requiring another review.")
        page.locator("#save-note").click()
        expect(page.locator("#revision-badge")).to_have_text("Revision 2")
        expect(page.locator("#run-checks")).to_be_disabled()
        expect(page.locator("#findings")).to_contain_text("No findings yet")
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(output / "03-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile horizontal overflow"
        browser.close()
    assert not errors, errors
    print("PASS: create, approval gate, pharmacy + billing, download, persistence, revision invalidation, mobile layout; no browser errors.")


if __name__ == "__main__":
    main()
