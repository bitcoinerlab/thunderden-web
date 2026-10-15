"""Exercise getUserMedia -> emulated UVC -> original Thunderden QR scanner.

Chromium's fake webcam displays a public fixture QR; the real browser camera API,
canvas conversion and emulator path are used. No physical camera is accessed.
Requires Python Playwright, Chromium, ffmpeg, qrencode and tesseract. Start the
local website first. Only the well-known abandon/about BIP39 fixture is entered.
"""

import argparse
import json
from pathlib import Path
import re
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
address = "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
subprocess.run(["qrencode", "-s", "8", "-m", "4", "-o", str(out / "qr.png"), address], check=True)
subprocess.run([
    "ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "10",
    "-i", str(out / "qr.png"), "-vf", "pad=640:480:(ow-iw)/2:(oh-ih)/2:color=white,format=yuv420p",
    "-frames:v", "10", "-f", "yuv4mpegpipe", str(out / "camera.y4m"),
], check=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=[
        "--use-fake-device-for-media-stream",
        f"--use-file-for-fake-video-capture={out / 'camera.y4m'}",
    ])
    context = browser.new_context(viewport={"width": 1360, "height": 1440})
    page = context.new_page()
    errors = []
    console = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: console.append(f"{message.type}: {message.text}"))
    started = time.monotonic()
    try:
        page.goto(args.url)
        page.locator("#boot").click()
        page.wait_for_function("!document.querySelector('#camera').disabled", timeout=60000)

        # Rejection is recoverable: it must neither stop the VM nor leave capture on.
        context.grant_permissions([], origin=args.url)
        assert page.evaluate("navigator.permissions.query({name:'camera'}).then(p => p.state)") == "denied"
        page.locator("#camera").click()
        page.wait_for_function("document.querySelector('#camera-status').textContent.includes('permission denied')")
        assert not page.locator("#status").inner_text().startswith("Stopped:")
        assert page.evaluate("document.querySelector('#camera-video').srcObject === null")
        print("PASS: permission denial leaves the VM running and can be retried", flush=True)

        context.grant_permissions(["camera"], origin=args.url)
        page.locator("#camera").click()
        page.wait_for_function("document.querySelector('#camera').textContent === 'Stop camera'", timeout=30000)
        assert page.evaluate("document.querySelector('#camera-video').videoWidth > 0")
        assert page.evaluate("document.querySelector('#camera-video').srcObject.getAudioTracks().length") == 0

        def wait_for(text, name, timeout=180):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                status = page.locator("#status").inner_text()
                assert not status.startswith("Stopped:"), status
                assert not errors, errors
                assert page.locator("#camera").inner_text() == "Stop camera", page.locator("#camera-status").inner_text()
                capture = out / "screen.png"
                page.locator("#screen").screenshot(path=str(capture))
                ocr = subprocess.run(["tesseract", str(capture), "stdout", "--psm", "11"],
                                     capture_output=True, text=True, check=True).stdout
                (out / "screen.txt").write_text(ocr)
                # This console font's slashed zero is read as 8. Word 18 cannot
                # exist in a 12-word phrase. Keep the raw OCR artifact unchanged.
                recognized = re.sub(r"\bWord\s+18\s+of\s+12\b", "Word 10 of 12", ocr, flags=re.IGNORECASE)
                if text.casefold() in recognized.casefold():
                    capture.replace(out / f"{name}.png")
                    print(f"Reached {name} after {time.monotonic() - started:.1f}s", flush=True)
                    return
                assert "could not complete this step" not in ocr.casefold(), ocr
                time.sleep(1)
            raise TimeoutError(f"Did not see {text!r}; inspect {out}")

        wait_for("Choose a Bitcoin network", "network")
        page.locator("#screen").focus()
        page.keyboard.press("Enter")  # Mainnet, public test wallet only.
        wait_for("What would you like to do", "menu")
        page.keyboard.press("Enter")
        wait_for("Generate new recovery words", "recovery-choice")
        page.keyboard.press("Enter")
        wait_for("How many words", "word-count")
        page.keyboard.press("Enter")
        for index, word in enumerate(["abandon"] * 11 + ["about"], 1):
            wait_for(f"Word {index} of 12", f"word-{index}")
            page.keyboard.type(word, delay=100)
            page.keyboard.press("Enter")
        wait_for("Wallet passphrase", "passphrase")
        page.keyboard.press("Enter")
        wait_for("Account number", "webcam-qr-decoded")
        page.keyboard.press("Enter")
        wait_for("Address verified", "address-verified")

        page.evaluate("window.cameraTestTracks = document.querySelector('#camera-video').srcObject.getTracks()")
        page.locator("#camera").click()
        assert page.locator("#camera").inner_text() == "Enable camera"
        assert page.evaluate("window.cameraTestTracks.every(track => track.readyState === 'ended')")
        assert page.evaluate("document.querySelector('#camera-video').srcObject === null")
        page.locator("#camera").click()
        page.wait_for_function("document.querySelector('#camera').textContent === 'Stop camera'")
        page.evaluate("document.querySelector('#camera-video').srcObject.getVideoTracks()[0].dispatchEvent(new Event('ended'))")
        assert "disconnected" in page.locator("#camera-status").inner_text()
        assert page.evaluate("document.querySelector('#camera-video').srcObject === null")
        assert page.locator("#camera").inner_text() == "Enable camera"
        assert not errors, errors
        print("PASS: getUserMedia QR verified by the original image; stop/restart/disconnection release the camera")
    except Exception:
        print(json.dumps({
            "status": page.locator("#status").inner_text(),
            "camera": page.locator("#camera-status").inner_text(),
            "diagnostics": page.locator("#log").inner_text(),
            "page_errors": errors, "console": console[-30:],
        }, indent=2))
        raise
    finally:
        browser.close()
