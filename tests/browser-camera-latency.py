"""Measure fresh camera-frame latency, not just virtual screen refresh rate.

Requires Python Playwright, Chromium and tesseract, with the website running.
Only Chromium's synthetic camera and the public abandon/about BIP39 fixture are
used. Eight vertical bars encode a frame counter; no physical webcam is accessed.
The counter repeats every 25.6 seconds, so longer delays are ambiguous.
"""

import argparse
import json
from pathlib import Path
import re
import statistics
import subprocess
import time

from playwright.sync_api import sync_playwright
from browser_screen import capture_guest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--url", default="http://127.0.0.1:4173")
parser.add_argument("--chromium")
parser.add_argument("--seconds", type=int, default=60)
parser.add_argument("--max-frame-age-ms", type=float, help="Optional median latency budget for a suitable test system")
parser.add_argument("--max-p95-frame-age-ms", type=float, help="Optional p95 latency budget for a suitable test system")
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
video = out / "counter.y4m"
with video.open("wb") as stream:
    stream.write(b"YUV4MPEG2 W640 H480 F10:1 Ip A1:1 C420jpeg\n")
    for counter in range(256):
        row = bytes([235]) * 64
        for bit in range(8):
            row += bytes([235 if counter & (1 << bit) else 16]) * 64
        row += bytes([16]) * 64
        stream.write(b"FRAME\n" + row * 480 + bytes([128]) * (640 * 480 // 2))

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=[
        "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
        f"--use-file-for-fake-video-capture={video}",
    ])
    page = browser.new_page(viewport={"width": 1360, "height": 1440})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def wait_for(text, timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            assert not errors, errors
            assert not page.locator("#status").inner_text().startswith("Stopped:")
            capture = out / "screen.png"
            capture_guest(page, capture)
            ocr = subprocess.run(["tesseract", str(capture), "stdout", "--psm", "11"],
                                 capture_output=True, text=True, check=True).stdout
            (out / "screen.txt").write_text(ocr)
            recognized = re.sub(r"\bWord\s+18\s+of\s+12\b", "Word 10 of 12", ocr, flags=re.IGNORECASE)
            if text.casefold() in recognized.casefold():
                return
            assert "could not complete this step" not in ocr.casefold(), ocr
            time.sleep(.5)
        raise TimeoutError(f"Did not see {text!r}; inspect {out}")

    try:
        page.goto(args.url)
        page.wait_for_function("!document.querySelector('#camera').disabled", timeout=60000)
        page.locator("#camera").click()
        page.wait_for_function("document.querySelector('#camera').textContent === 'Stop camera'")
        wait_for("Choose a Bitcoin network")
        page.locator("#screen").focus()
        page.keyboard.press("Enter")
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
        page.keyboard.press("Enter")
        page.wait_for_timeout(15000)  # Warm the guest renderer before sampling.
        wait_for("scanned")
        page.evaluate("""() => {
            const video = document.querySelector('#camera-video');
            const screen = document.querySelector('#screen');
            const canvas = document.createElement('canvas');
            canvas.width = 10; canvas.height = 2;
            const context = canvas.getContext('2d', {willReadFrequently: true});
            context.imageSmoothingEnabled = false;
            const seen = new Map();
            const samples = [];
            let timer;
            function counter(row) {
                const pixels = context.getImageData(0, row, 10, 1).data;
                let value = 0;
                for (let bit = 0; bit < 8; bit++) {
                    if (pixels[(bit + 1) * 4] > 128) value |= 1 << bit;
                }
                return value;
            }
            function capture() {
                context.drawImage(video, 0, video.videoHeight / 2, video.videoWidth, 1, 0, 0, 10, 1);
                seen.set(counter(0), performance.now());
                timer = setTimeout(capture, 16);
            }
            capture();
            const observer = new MutationObserver(() => {
                // These are the original guest's font-dependent preview bounds.
                const caption = screen.width >= 1280 && screen.height >= 768 ? 88
                    : screen.width >= 800 && screen.height >= 432 ? 60 : 56;
                const height = screen.height - caption;
                const width = Math.min(screen.width, Math.floor(640 * height / 480));
                const x = Math.floor((screen.width - width) / 2);
                context.drawImage(screen, x, Math.floor(height * .25), width, 1, 0, 0, 10, 1);
                context.drawImage(screen, x, Math.floor(height * .75), width, 1, 0, 1, 10, 1);
                const upper = counter(0), lower = counter(1);
                // Reject a frame being painted between the two sampled rows.
                if (upper === lower && seen.has(upper)) {
                    samples.push({time: performance.now(), code: upper, age: performance.now() - seen.get(upper)});
                }
            });
            observer.observe(screen, {attributes: true, attributeFilter: ['data-frames']});
            window.finishLatencySample = () => {
                clearTimeout(timer); observer.disconnect(); return samples;
            };
        }""")
        page.wait_for_timeout(args.seconds * 1000)
        samples = page.evaluate("window.finishLatencySample()")
        assert samples, "No coherent numbered camera frames were observed"
        ages = sorted(sample["age"] for sample in samples)
        changed = [sample for index, sample in enumerate(samples)
                   if index == 0 or sample["code"] != samples[index - 1]["code"]]
        report = {"samples": len(samples), "median_frame_age_ms": statistics.median(ages),
                  "p95_frame_age_ms": ages[min(len(ages) - 1, int(len(ages) * .95))],
                  "max_frame_age_ms": max(ages), "complete_frame_changes_per_second": len(changed) / args.seconds}
        (out / "latency-samples.json").write_text(json.dumps(samples))
        (out / "latency.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2), flush=True)
        assert not errors, errors
        assert page.locator("#camera").inner_text() == "Stop camera"
        assert not page.locator("#status").inner_text().startswith("Stopped:")
        if args.max_frame_age_ms is not None:
            assert report["median_frame_age_ms"] <= args.max_frame_age_ms, "Camera frame age exceeded the test budget"
        if args.max_p95_frame_age_ms is not None:
            assert report["p95_frame_age_ms"] <= args.max_p95_frame_age_ms, "Camera p95 frame age exceeded the test budget"
        page.locator("#screen").focus()
        page.keyboard.press("Escape")
        wait_for("What would you like to do", timeout=60)
        print("PASS: measured numbered camera frames and cancelled the original scanner")
    finally:
        (out / "browser-state.json").write_text(json.dumps({
            "status": page.locator("#status").inner_text(),
            "camera": page.locator("#camera-status").inner_text(),
            "diagnostics": page.locator("#log").inner_text(),
            "errors": errors,
        }, indent=2))
        browser.close()
