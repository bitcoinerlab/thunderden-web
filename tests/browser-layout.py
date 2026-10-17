"""Check the laptop scene and in-screen loading at different viewport sizes.

Requires Python Playwright and Chromium, with the website running. Downloads are
held pending so the real boot cover can be inspected without starting a guest.
Viewport emulation is not validation of mobile browsers or touch input.
"""

import argparse
import json
from pathlib import Path

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
    page = browser.new_page()
    errors = []
    requests = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/assets/thunderden.img", lambda route: requests.append(route))
    page.route("**/emulator/qemu-system-x86_64.wasm", lambda route: requests.append(route))
    results = []

    def fits(rect, width, height):
        return rect["x"] >= -1 and rect["y"] >= -1 and rect["right"] <= width + 1 and rect["bottom"] <= height + 1

    try:
        for width, height in [(1920, 1080), (1440, 900), (1366, 768), (1280, 720),
                              (1024, 768), (800, 600), (390, 844), (360, 640), (844, 390)]:
            page.set_viewport_size({"width": width, "height": height})
            if not results:
                page.goto(args.url)
                page.wait_for_function("document.querySelector('#startup-image').dataset.state === 'active'")
                page.wait_for_function("document.querySelector('#startup-wasm').dataset.state === 'active'")
            state = page.evaluate("""() => {
                const rect = selector => {
                    const r = document.querySelector(selector).getBoundingClientRect();
                    return {x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom};
                };
                const card = document.querySelector('.boot-card');
                return {screen: rect('#screen'), device: rect('#device'), cover: rect('#boot-cover'),
                    title: rect('#boot-title'), imageProgress: rect('#image-progress'), wasmProgress: rect('#wasm-progress'),
                    keyboardGuide: rect('#keyboard-guide'),
                    guideFont: parseFloat(getComputedStyle(document.querySelector('#keyboard-instructions')).fontSize),
                    titleFont: parseFloat(getComputedStyle(document.querySelector('#boot-title')).fontSize),
                    statsFont: parseFloat(getComputedStyle(document.querySelector('#startup small')).fontSize),
                    spinnerWidth: rect('.boot-spinner').width,
                    cardScroll: card.scrollHeight - card.clientHeight,
                    pageWidth: document.documentElement.scrollWidth,
                    art: getComputedStyle(document.querySelector('.laptop-art')).display};
            }""")
            assert fits(state["screen"], width, height), state
            assert state["screen"]["width"] >= 250 and state["screen"]["height"] >= 180, state
            assert state["pageWidth"] <= width, state
            assert state["titleFont"] >= 20 and state["spinnerWidth"] >= 30, state
            assert state["guideFont"] >= 13, state
            if state["screen"]["height"] > 340:
                assert state["statsFont"] >= 14, state
                assert state["guideFont"] >= 18, state
            assert page.evaluate("window.scrollY") == 0
            assert page.locator("#boot-cover").is_visible()
            for name in ["title", "imageProgress", "wasmProgress", "keyboardGuide"]:
                assert fits(state[name], width, height), state
                assert state[name]["bottom"] <= state["cover"]["bottom"], state
            if width > 700 and height > 560:
                assert fits(state["device"], width, height), state
                assert state["art"] != "none", state
                assert state["cardScroll"] <= 1, state
            page.screenshot(path=str(out / f"loading-{width}x{height}.png"))
            results.append({"viewport": [width, height], **state})

        assert len(requests) == 2, requests  # No click and no duplicate boot on resize.
        assert page.evaluate("document.querySelector('#camera-video').srcObject === null")
        assert page.locator("#camera-led").get_attribute("data-active") == "false"
        assert "Click outside" in page.locator("#keyboard-guide").inner_text()
        assert page.locator("#startup li").count() == 2
        # Inspect live SVG text metrics: every legend must fit its own keycap.
        artwork = page.evaluate("""async () => {
            const source = await (await fetch('./laptop.svg')).text();
            const svg = new DOMParser().parseFromString(source, 'image/svg+xml').documentElement;
            svg.style.cssText = 'position:fixed;left:-2000px;width:1120px;height:830px;opacity:0;pointer-events:none';
            document.body.append(svg);
            try {
                const keys = [...svg.querySelectorAll('.key')];
                const overflow = keys.filter(key => {
                    const cap = key.querySelector('use');
                    const box = cap.getBBox();
                    const matrix = cap.transform.baseVal.consolidate().matrix;
                    const left = new DOMPoint(box.x, box.y).matrixTransform(matrix);
                    const right = new DOMPoint(box.x + box.width, box.y + box.height).matrixTransform(matrix);
                    const text = key.querySelector('text').getBBox();
                    return text.x < left.x || text.x + text.width > right.x
                        || text.y < left.y || text.y + text.height > right.y;
                }).map(key => key.textContent);
                return {keys: keys.length, overflow};
            } finally { svg.remove(); }
        }""")
        assert artwork["keys"] == 78 and not artwork["overflow"], artwork
        page.locator("#about").click()
        assert page.locator("#about-dialog").is_visible()
        page.keyboard.press("Escape")
        assert page.locator("#about-dialog").is_hidden()
        assert not errors, errors
        (out / "layout.json").write_text(json.dumps(results, indent=2))
        print("PASS: readable loading UI and initial screen/laptop fit across nine Chromium viewports; all 78 key legends fit their keycaps")
    finally:
        for route in requests:
            route.abort()
        browser.close()
