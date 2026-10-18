"""Boot the real image in the page and navigate with browser keyboard events.

Requires Python Playwright, Chromium and tesseract. No recovery words are entered.
Run npm run setup and npm start before this test.
"""

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import time

from playwright.sync_api import sync_playwright
from browser_screen import capture_guest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--url", default="http://127.0.0.1:4173")
parser.add_argument("--chromium")
parser.add_argument("--max-frame-interval-ms", type=float,
                     help="Optional median display-refresh budget; omit for functional checks on slow systems")
parser.add_argument("--max-boot-seconds", type=float, help="Optional page-load-to-network-menu budget for a suitable test system")
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=args.chromium, headless=True)
    page = browser.new_page(viewport={"width": 1366, "height": 768})
    errors = []
    console = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: console.append(f"{message.type}: {message.text}"))
    started = time.monotonic()
    try:
        page.goto(args.url)
        assert page.locator("#camera").is_disabled()
        assert page.locator("#boot-cover").is_visible()
        assert page.locator("#keyboard-prompt").is_hidden()
        assert page.locator("#boot-cover #keyboard-instructions").count() == 0

        def wait_for(text, name, timeout=600):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                status = page.locator("#status").inner_text()
                assert not status.startswith("Stopped:"), status
                assert not errors, errors
                capture = out / "screen.png"
                capture_guest(page, capture)
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
        elapsed = time.monotonic() - started
        assert page.locator("#screen").get_attribute("data-ready") == "true"
        assert page.locator("#boot-cover").is_hidden()
        assert page.locator("#boot-controls").is_hidden()
        assert page.locator("#screen").evaluate("screen => !screen.inert")
        assert page.locator("#screen").get_attribute("data-keyboard") == "released"
        assert page.locator("#screen").evaluate("screen => document.activeElement !== screen")
        assert page.locator("#keyboard-prompt").is_visible()
        assert page.locator("#screen").get_attribute("tabindex") == "-1"
        guide = page.locator("#keyboard-prompt").inner_text()
        assert "Thunder Den is ready" in guide and "Click outside" in guide
        assert "capture keyboard input" in guide
        assert "navigate" in guide and "Esc" in guide and "Use keyboard" not in guide
        assert page.locator("#keyboard-prompt").evaluate("prompt => getComputedStyle(prompt).backdropFilter") == "blur(2px)"
        assert page.evaluate("""() => {
            const screen = document.querySelector('#screen').getBoundingClientRect();
            const prompt = document.querySelector('#keyboard-prompt').getBoundingClientRect();
            return prompt.left >= screen.left && prompt.top >= screen.top
                && prompt.right <= screen.right && prompt.bottom <= screen.bottom;
        }""")
        page.screenshot(path=str(out / "laptop-ready.png"))
        (out / "boot-timing.json").write_text(json.dumps({"seconds_to_network_menu": elapsed}, indent=2))
        if args.max_boot_seconds is not None:
            assert elapsed <= args.max_boot_seconds, "Guest boot exceeded the test budget"
        page.evaluate("""() => {
            window.displayIntervals = [];
            let previous = performance.now();
            window.displayObserver = new MutationObserver(() => {
                const now = performance.now();
                window.displayIntervals.push(now - previous);
                previous = now;
            });
            window.displayObserver.observe(document.querySelector('#screen'), {
                attributes: true, attributeFilter: ['data-frames'],
            });
        }""")
        page.wait_for_function("window.displayIntervals.length >= 13", timeout=30000)
        intervals = page.evaluate("() => { window.displayObserver.disconnect(); return window.displayIntervals.slice(1); }")
        median = statistics.median(intervals)
        (out / "display-timing.json").write_text(json.dumps({"intervals_ms": intervals, "median_ms": median}, indent=2))
        print(f"Median display refresh: {median:.1f} ms ({1000 / median:.1f} updates/s)", flush=True)
        if args.max_frame_interval_ms is not None:
            assert median <= args.max_frame_interval_ms, f"Display refresh exceeded {args.max_frame_interval_ms} ms: {median:.1f} ms"
        # Mouse focus must show the orange border before any key is pressed.
        def observe_input():
            page.evaluate("""async () => {
                const { Qmp } = await import('./qmp.js');
                const command = Qmp.prototype.command;
                window.testInputEvents = [];
                Qmp.prototype.command = function(name, args, ...rest) {
                    if (name === 'input-send-event') window.testInputEvents.push(...args.events);
                    return command.call(this, name, args, ...rest);
                };
            }""")

        observe_input()
        # The entire display is clickable, not just the instruction text.
        page.locator("#keyboard-prompt").click(position={"x":12,"y":12})
        assert page.locator("#screen").get_attribute("data-keyboard") == "active"
        assert page.locator("#keyboard-prompt").is_hidden()
        assert page.locator("#screen").get_attribute("tabindex") == "0"
        assert page.locator("#screen").evaluate("screen => getComputedStyle(screen).filter") == "none"
        assert page.locator("#screen").evaluate("screen => getComputedStyle(screen).outlineColor") == "rgb(223, 156, 67)"
        assert page.evaluate("window.testInputEvents.length") == 0
        assert "Click outside" in page.locator("#keyboard-status").inner_text()
        page.screenshot(path=str(out / "keyboard-active.png"))
        page.keyboard.down("Shift")
        # A blank, non-focusable part of the scene must release a held modifier too.
        page.locator(".scene").click(position={"x": 5, "y": 5})
        assert page.locator("#screen").get_attribute("data-keyboard") == "released"
        assert page.locator("#keyboard-prompt").is_hidden()
        assert page.locator("#screen").evaluate("screen => getComputedStyle(screen).outlineStyle") == "none"
        assert page.evaluate("window.testInputEvents") == [
            {"type": "key", "data": {"down": True, "key": {"type": "qcode", "data": "shift"}}},
            {"type": "key", "data": {"down": False, "key": {"type": "qcode", "data": "shift"}}},
        ]
        page.keyboard.up("Shift")
        page.keyboard.press("ArrowDown")
        assert page.evaluate("window.testInputEvents.length") == 2
        page.screenshot(path=str(out / "keyboard-released.png"))
        page.locator("#screen").click()
        assert page.locator("#screen").get_attribute("data-keyboard") == "active"
        assert page.locator("#screen").evaluate("screen => getComputedStyle(screen).outlineColor") == "rgb(223, 156, 67)"
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
        for activation in ("Enter", "Space"):
            page.reload()
            page.wait_for_function("document.querySelector('#screen').dataset.ready === 'true'", timeout=90000)
            assert page.locator("#keyboard-prompt").is_visible()
            observe_input()
            page.locator("#about").focus()
            page.keyboard.press("Tab")
            assert page.locator("#keyboard-prompt").evaluate("prompt => document.activeElement === prompt")
            page.keyboard.press(activation)
            assert page.locator("#keyboard-prompt").is_hidden()
            assert page.locator("#screen").get_attribute("data-keyboard") == "active"
            assert page.evaluate("window.testInputEvents") == [], "Help activation reached the guest"
            page.locator(".scene").click(position={"x":5,"y":5})
            assert page.locator("#keyboard-prompt").is_hidden(), "Help returned after releasing focus"
            assert page.locator("#screen").get_attribute("data-keyboard") == "released"
        print("PASS: real guest navigation; click-to-focus border, outside-click release and held-key cleanup")
        print("PASS: one-time ready guidance; pointer, Enter and Space activation do not forward input to the guest")
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
