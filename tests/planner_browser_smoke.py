#!/usr/bin/env python3
import contextlib
import http.server
import socketserver
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PORT = 8123

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

@contextlib.contextmanager
def serve_site():
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(SITE), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.25)
        try:
            yield
        finally:
            httpd.shutdown()
            thread.join(timeout=2)

def assert_planner_rendered(page, label):
    page.wait_for_timeout(9000)
    status = page.locator("#ps-status")
    if status.count():
        raise AssertionError(f"{label}: planner status bleef staan: {status.inner_text()!r}")
    if page.locator(".ps-summary").count() != 1:
        raise AssertionError(f"{label}: .ps-summary ontbreekt")
    price_slots = page.locator(".ps-price-col").count()
    balance_slots = page.locator(".ps-balance-col").count()
    if price_slots != 96:
        raise AssertionError(f"{label}: verwacht 96 price slots, kreeg {price_slots}")
    if balance_slots != 96:
        raise AssertionError(f"{label}: verwacht 96 balance slots, kreeg {balance_slots}")


def main():
    errors = []
    console_errors = []
    with serve_site(), sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        try:
            page.goto(f"http://127.0.0.1:{PORT}/planner-shadow/", wait_until="networkidle")
            assert_planner_rendered(page, "direct-load")

            page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
            planner_link = page.get_by_role("link", name="Planner Shadow")
            if planner_link.count() != 1:
                raise AssertionError("home: Planner Shadow navigatielink ontbreekt")
            planner_link.click()
            page.wait_for_load_state("networkidle")
            assert_planner_rendered(page, "home-to-planner")

            page.goto(f"http://127.0.0.1:{PORT}/energiehistorie/", wait_until="networkidle")
            page.goto(f"http://127.0.0.1:{PORT}/planner-shadow/", wait_until="networkidle")
            assert_planner_rendered(page, "round-trip")

            if errors:
                raise AssertionError("uncaught page errors: " + " | ".join(errors))
            if console_errors:
                raise AssertionError("console errors: " + " | ".join(console_errors))
        except Exception:
            page.screenshot(path="planner-smoke-failure.png", full_page=True)
            print("PAGE_ERRORS:", errors)
            print("CONSOLE_ERRORS:", console_errors)
            raise
        finally:
            browser.close()

if __name__ == "__main__":
    main()
