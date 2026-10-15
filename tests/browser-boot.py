"""Boot the real image in the page and navigate with browser keyboard events.

Requires Python Playwright, Chromium and tesseract. No recovery words are entered.
Run npm run setup and npm start before this test.
"""

import argparse
import json
from pathlib import Path
import subprocess
import time

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--url", default="http://127.0.0.1:4173")
parser.add_argument("--chromium")
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=args.chromium, headless=True)
    page = browser.new_page(viewport={"width": 1360, "height": 1200})
    errors = []
    console = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: console.append(f"{message.type}: {message.text}"))
    started = time.monotonic()
    try:
        page.goto(args.url)
        assert page.locator("#camera").is_disabled()
        page.locator("#boot").click()

        def wait_for(text, name, timeout=600):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                status = page.locator("#status").inner_text()
                assert not status.startswith("Stopped:"), status
                assert not errors, errors
                capture = out / "screen.png"
                page.locator("#screen").screenshot(path=str(capture))
                ocr = subprocess.run(["tesseract", str(capture), "stdout", "--psm", "11"],
                                     capture_output=True, text=True, check=True).stdout
                (out / "screen.txt").write_text(ocr)
                if text.casefold() in ocr.casefold():
                    capture.replace(out / f"{name}.png")
                    print(f"Reached {name} after {time.monotonic() - started:.1f}s", flush=True)
                    return ocr
                time.sleep(2)
            raise TimeoutError(f"Did not see {text!r}; inspect {out}")

        wait_for("Choose a Bitcoin network", "network")
        page.locator("#screen").focus()
        for _ in range(3):
            page.keyboard.press("ArrowDown")
            time.sleep(0.2)
        page.keyboard.press("Enter")
        menu = wait_for("What would you like to do", "menu", timeout=60)
        assert "regtest" in menu.casefold(), menu
        time.sleep(0.5)
        page.keyboard.press("ArrowDown")
        time.sleep(0.2)
        page.keyboard.press("Enter")
        wait_for("Choose a public key", "keyboard-navigation", timeout=60)
        page.keyboard.press("Escape")
        wait_for("What would you like to do", "returned-to-menu", timeout=60)
        assert page.evaluate("document.querySelector('#camera-video').srcObject === null")
        print("PASS: original release image boots in Chromium and accepts real browser keyboard input")
    except Exception:
        print(json.dumps({
            "status": page.locator("#status").inner_text(),
            "diagnostics": page.locator("#log").inner_text(),
            "page_errors": errors,
            "console": console[-30:],
        }, indent=2))
        raise
    finally:
        browser.close()
