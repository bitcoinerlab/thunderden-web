"""Check native camera collection and cancellation in the unchanged release.

Requires Python Playwright, Chromium and tesseract, with the website running.
Uses only deterministic public synthetic video, never a physical camera or wallet
material. Cancels before generating any words. By default, stops after collection;
--wait-assessment checks control responsiveness until the guest reports an outcome.
This does not assert NIST completion, entropy quality or secure wallet generation.
"""

import argparse
import json
from pathlib import Path
import random
import re
import subprocess
import time

from playwright.sync_api import Error as PlaywrightError, sync_playwright
from browser_screen import capture_guest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--url", default="http://127.0.0.1:4173")
parser.add_argument("--chromium")
parser.add_argument("--wait-assessment", action="store_true",
                    help="Wait for the guest's assessment outcome, including a reported timeout")
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
video = out / "public-noise.y4m"
rng = random.Random(0x7468756E646572)  # Public fixture seed, not a randomness source.
luminance = bytes(16 + value % 220 for value in range(256))
with video.open("wb") as stream:
    stream.write(b"YUV4MPEG2 W640 H480 F10:1 Ip A1:1 C420jpeg\n")
    for _ in range(128):
        stream.write(b"FRAME\n" + rng.randbytes(640 * 480).translate(luminance)
                     + bytes([128]) * (640 * 480 // 2))

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=[
        "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
        f"--use-file-for-fake-video-capture={video}",
    ])
    page = browser.new_page(viewport={"width": 1366, "height": 768})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def screen_text():
        assert not errors, errors
        status = page.locator("#status").inner_text()
        assert not status.startswith("Stopped:"), status
        capture_guest(page, out / "screen.png")
        text = subprocess.run(["tesseract", str(out / "screen.png"), "stdout", "--psm", "11"],
                              capture_output=True, text=True, check=True).stdout
        (out / "screen.txt").write_text(text)
        return re.sub(r"\s+", " ", text).casefold()

    def wait_for(text, timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if text.casefold() in screen_text():
                return
            page.wait_for_timeout(500)
        raise TimeoutError(f"Did not see {text!r}; inspect {out}")

    try:
        page.goto(args.url)
        page.wait_for_function("!document.querySelector('#camera').disabled", timeout=60000)
        page.locator("#camera").click()
        page.wait_for_function("document.querySelector('#camera-led').dataset.active === 'true'")
        wait_for("Choose a Bitcoin network")
        page.locator("#screen").click()
        for key, expected in [
            ("4", "What would you like to do"),  # Regtest; no coins or wallet.
            ("1", "Generate new recovery words"),
            ("2", "How many recovery words"),
            ("1", "How your recovery words are created"),
            ("Enter", "Add randomness from your camera"),
            ("1", "Add coin tosses or dice rolls"),
            ("1", "Collect camera randomness"),
        ]:
            page.keyboard.press(key)
            wait_for(expected)
        started = time.monotonic()
        page.keyboard.press("Enter")
        checks_started = False
        deadline = started + 180
        while time.monotonic() < deadline:
            text = screen_text()
            assert "camera not included" not in text, text
            assert "write down your recovery words" not in text, "Unexpected generation screen"
            checks_started |= "randomness checks: running" in text
            if "camera: finished" in text or "camera data ready" in text or "camera checks returned a warning" in text:
                break
            page.wait_for_timeout(500)
        else:
            raise TimeoutError("Camera collection did not finish")
        assert checks_started, "NIST assessment did not start receiving camera samples"
        capture_guest(page, out / "collection-finished.png")
        report = {
            "seconds_to_collection_finished": time.monotonic() - started,
            "assessment_started": checks_started, "assessment_completion_tested": False,
        }
        (out / "collection.json").write_text(json.dumps(report, indent=2))
        if args.wait_assessment:
            deadline = started + 210
            while time.monotonic() < deadline:
                text = screen_text()
                assert "write down your recovery words" not in text, "Unexpected generation screen"
                if any(label in text for label in ["camera not included", "camera data ready", "camera checks returned a warning"]):
                    report["guest_outcome"] = text
                    report["assessment_completion_tested"] = True
                    report["assessment_outcome"] = "rejected" if "camera not included" in text else (
                        "warning" if "camera checks returned a warning" in text else "ready")
                    (out / "collection.json").write_text(json.dumps(report, indent=2))
                    capture_guest(page, out / "assessment-outcome.png")
                    break
                page.wait_for_timeout(500)
            else:
                raise TimeoutError("Guest did not report an assessment outcome")
        page.keyboard.press("Escape")
        wait_for("What would you like to do", timeout=60)
        print("PASS: native camera collection completed and assessment started; cancelled without generating recovery words")
        if args.wait_assessment:
            print("PASS: emulator controls remained responsive through the guest outcome; "
                  f"assessment_outcome={report['assessment_outcome']}")
    finally:
        try:
            state = page.evaluate("""() => ({
                status: document.querySelector('#status')?.textContent,
                camera: document.querySelector('#camera-status')?.textContent,
                diagnostics: document.querySelector('#log')?.textContent,
            })""")
        except PlaywrightError as error:
            state = {"diagnostic_error": str(error)}
        (out / "browser-state.json").write_text(json.dumps({**state, "errors": errors}, indent=2))
        browser.close()
