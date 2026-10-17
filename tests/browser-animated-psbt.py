"""Scan an animated public PSBT through getUserMedia and the unchanged image.

Requires Python Playwright, Pillow, Chromium, qrencode and tesseract, with the
website running. Uses only the public abandon/about fixture and synthetic coins.
Stops at transaction review and cancels; it does not approve signing or broadcast.
"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import time

from PIL import Image
from playwright.sync_api import sync_playwright
from browser_screen import capture_guest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--url", default="http://127.0.0.1:4173")
parser.add_argument("--chromium")
parser.add_argument("--max-review-seconds", type=float, help="Optional scan-to-review budget for a suitable test system")
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
fixture = json.loads((Path(__file__).parent / "fixtures/animated-psbt.json").read_text())
video = out / "animated.y4m"
with video.open("wb") as stream:
    stream.write(b"YUV4MPEG2 W640 H480 F10:1 Ip A1:1 C420jpeg\n")
    for text in fixture["frames"]:
        subprocess.run(["qrencode", "-s", "6", "-m", "4", "-o", str(out / "qr.png"), text], check=True)
        with Image.open(out / "qr.png") as qr:
            qr = qr.convert("RGBA").convert("L").point(lambda value: 16 + value * 219 // 255)
            assert qr.width <= 640 and qr.height <= 480
            frame = Image.new("L", (640, 480), 235)
            frame.paste(qr, ((640 - qr.width) // 2, (480 - qr.height) // 2))
            stream.write(b"FRAME\n" + frame.tobytes() + bytes([128]) * (640 * 480 // 2))

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=[
        "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
        f"--use-file-for-fake-video-capture={video}",
    ])
    page = browser.new_page(viewport={"width": 1360, "height": 1440})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def wait_for(*texts, timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            assert not errors, errors
            status = page.locator("#status").inner_text()
            assert not status.startswith("Stopped:"), status
            capture = out / "screen.png"
            capture_guest(page, capture)
            ocr = subprocess.run(["tesseract", str(capture), "stdout", "--psm", "11"],
                                 capture_output=True, text=True, check=True).stdout
            (out / "screen.txt").write_text(ocr)
            recognized = re.sub(r"\bWord\s+18\s+of\s+12\b", "Word 10 of 12", ocr, flags=re.IGNORECASE)
            if all(text.casefold() in recognized.casefold() for text in texts):
                return ocr
            assert "could not complete this step" not in ocr.casefold(), ocr
            assert "no matching signing key" not in ocr.casefold(), ocr
            time.sleep(.5)
        raise TimeoutError(f"Did not see {texts!r}; inspect {out}")

    try:
        page.goto(args.url)
        page.wait_for_function("!document.querySelector('#camera').disabled", timeout=60000)
        page.locator("#camera").click()
        page.wait_for_function("document.querySelector('#camera').textContent === 'Stop camera'")
        wait_for("Choose a Bitcoin network")
        page.locator("#screen").focus()
        page.keyboard.press("Enter")  # Mainnet serialization, synthetic coins only.
        wait_for("What would you like to do")
        page.keyboard.press("Enter")
        wait_for("Generate new recovery words")
        page.keyboard.press("Enter")
        wait_for("How many words")
        page.keyboard.press("Enter")
        for index, word in enumerate(["abandon"] * 11 + ["about"], 1):
            wait_for(f"Word {index} of 12")
            page.keyboard.type(word, delay=100)
            page.keyboard.press("Enter")
        wait_for("Wallet passphrase")
        started = time.monotonic()
        page.keyboard.press("Enter")
        expected = ["Review transaction"] + [
            f"{fixture[name]} sats" for name in ["payment_sats", "change_sats", "fee_sats"]
        ]
        wait_for(*expected)
        elapsed = time.monotonic() - started
        assert page.locator("#camera").inner_text() == "Stop camera"
        capture_guest(page, out / "review.png")
        result = {"seconds_to_review": elapsed, "bytes": fixture["bytes"], "parts": fixture["parts"]}
        (out / "result.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2), flush=True)
        if args.max_review_seconds is not None:
            assert elapsed <= args.max_review_seconds, "Animated PSBT exceeded the scan-to-review budget"
        page.keyboard.press("Escape")
        wait_for("What would you like to do")
        print("PASS: animated public PSBT reached review with the expected amounts and fee; cancelled without signing")
    finally:
        (out / "browser-state.json").write_text(json.dumps({
            "status": page.locator("#status").inner_text(),
            "camera": page.locator("#camera-status").inner_text(),
            "diagnostics": page.locator("#log").inner_text(),
            "errors": errors,
        }, indent=2))
        browser.close()
