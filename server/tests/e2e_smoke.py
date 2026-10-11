"""Browser smoke test (optional): loads every view, records a sale, and checks the re-plan updates.

Needs: pip install playwright && playwright install chromium, the built client (client/dist), and a running server.
Usage: python tests/e2e_smoke.py [base_url] [screenshot_dir]
Run it against a throwaway database (AUCTION_DB=/tmp/test.db python -m app) because it records and undoes a sale.
"""
import sys

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else None


def shot(page, name):
    if SHOTS:
        page.screenshot(path=f"{SHOTS}/{name}.png", full_page=False)


def main():
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        # Network failures (blocked web fonts, the deliberate 409 below) show as console errors; real script errors arrive via pageerror.
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)

        page.goto(f"{BASE}/#/board")
        expect(page.get_by_text("Nikola Jokic").first).to_be_visible(timeout=15000)
        page.get_by_label("Find player").fill("Maxey")
        expect(page.locator("tbody tr").filter(has_text="Tyrese Maxey")).to_have_count(1)
        page.get_by_label("Find player").fill("")
        shot(page, "1-board")

        page.goto(f"{BASE}/#/stats")
        expect(page.get_by_role("button", name="Stat rk")).to_be_visible()
        page.get_by_role("button", name="Stat rk").click()
        shot(page, "2-stats")

        page.goto(f"{BASE}/#/teams")
        expect(page.locator(".team").first).to_be_visible(timeout=120000)
        expect(page.locator(".team")).to_have_count(12, timeout=120000)
        shot(page, "3-teams")

        page.goto(f"{BASE}/#/draft")
        expect(page.get_by_text("Working out your best roster").or_(page.locator(".plan").first)).to_be_visible()
        expect(page.locator("[aria-label='Your team'] .plan")).to_be_visible(timeout=30000)
        before = page.locator("[aria-label='Your team'] .kv b").nth(3).inner_text()
        page.get_by_label("Player nominated").fill("Wemb")
        page.get_by_role("option").first.click()
        expect(page.locator(".bidcard .name")).to_have_text("Victor Wembanyama")
        page.get_by_role("button", name="If I win at").click()
        expect(page.locator(".whatif")).to_be_visible(timeout=30000)
        page.get_by_label("Price").fill("80")
        page.get_by_label("Won by").select_option(value="1")
        page.get_by_role("button", name="Record sale").click()
        expect(page.locator(".list .item").filter(has_text="Victor Wembanyama")).to_be_visible()
        expect(page.get_by_text("×", exact=False).first).to_be_visible()
        page.wait_for_timeout(500)
        expect(page.locator("[aria-label='Your team'] .plan")).to_be_visible(timeout=30000)
        shot(page, "4-draft")
        # Over-budget sale is rejected with a readable message
        page.get_by_label("Player nominated").fill("Jokic")
        page.get_by_role("option").first.click()
        page.get_by_label("Price").fill("150")
        page.get_by_label("Won by").select_option(value="1")
        page.get_by_role("button", name="Record sale").click()
        expect(page.get_by_role("alert")).to_contain_text("can bid at most $112")
        page.get_by_role("button", name="Undo last").click()
        expect(page.get_by_text("No sales yet")).to_be_visible()

        page.goto(f"{BASE}/#/sources")
        expect(page.get_by_text("FantasyPros projections")).to_be_visible()
        shot(page, "5-sources")
        page.goto(f"{BASE}/#/settings")
        expect(page.get_by_label("Teams")).to_have_value("12")
        shot(page, "6-settings")

        page.set_viewport_size({"width": 400, "height": 860})
        page.goto(f"{BASE}/#/board")
        expect(page.get_by_text("Nikola Jokic").first).to_be_visible()
        overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        shot(page, "7-phone")
        browser.close()
    print("before re-plan cats:", before)
    if overflow:
        errors.append("Page scrolls sideways at phone width.")
    if errors:
        print("PROBLEMS:\n  " + "\n  ".join(errors))
        sys.exit(1)
    print("e2e smoke test passed")


if __name__ == "__main__":
    main()
