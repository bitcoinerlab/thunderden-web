"""Check startup progress, quiet boot cover, HTTP caching and clear failures.

Requires Python Playwright and Chromium, with the website running. Only the
unchanged public release image and deliberately invalid public test bytes are
used. No wallet material or physical camera is accessed.
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
    page = browser.new_page(viewport={"width": 1366, "height": 768})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    network = page.context.new_cdp_session(page)
    network.send("Network.enable")
    network.send("Network.emulateNetworkConditions", {
        "offline": False, "latency": 10,
        "downloadThroughput": 2 * 1024 * 1024, "uploadThroughput": 1024 * 1024,
    })

    def ready():
        page.wait_for_function("""() => document.querySelector('#startup').hidden
            || document.querySelector('#status').textContent.startsWith('Stopped:')""", timeout=180000)
        assert not page.locator("#status").inner_text().startswith("Stopped:"), page.locator("#status").inner_text()
        assert not errors, errors
        assert page.locator('#startup [data-state="done"]').count() == 2
        assert not page.locator("#camera").is_disabled()
        return page.evaluate("""() => ({
            phases: [...document.querySelectorAll('#startup li')].map(row => ({
                id: row.id, detail: row.querySelector('small').textContent,
                value: row.querySelector('progress').value,
            })),
            resources: performance.getEntriesByType('resource').filter(entry =>
                entry.name.endsWith('thunderden.img') || entry.name.endsWith('qemu-system-x86_64.wasm')
            ).map(entry => ({name: new URL(entry.name).pathname, start: entry.startTime, end: entry.responseEnd,
                encoded: entry.encodedBodySize, decoded: entry.decodedBodySize, transferred: entry.transferSize})),
        })""")

    try:
        page.goto(args.url)
        page.emulate_media(reduced_motion="reduce")
        assert page.locator("#startup").is_visible()
        assert page.locator("#boot-cover").is_visible()
        assert page.locator("#boot-estimate").is_hidden()
        assert page.locator("#keyboard-prompt").is_hidden()
        assert "Click the screen" in page.locator("#keyboard-guide").inner_text()
        assert "Click outside" in page.locator("#keyboard-guide").inner_text()
        assert page.locator("#startup li").count() == 2
        assert page.locator("#startup summary").count() == 0
        assert page.locator("#screen").evaluate("screen => screen.inert")
        assert page.locator('.boot-spinner').evaluate("spinner => getComputedStyle(spinner).animationName") == "none"
        page.wait_for_function("""() => { const bar = document.querySelector('#image-progress');
            return bar.hasAttribute('value') && bar.value > .05 && bar.value < .95; }""", timeout=60000)
        progress = page.evaluate("""() => ({
            value: document.querySelector('#image-progress').value,
            detail: document.querySelector('#startup-image small').textContent,
        })""")
        assert " / 64.0 MiB unpacked" in progress["detail"], progress
        assert progress["detail"].endswith(f"· {int(progress['value'] * 100)}%"), progress
        page.screenshot(path=str(out / "progress.png"))
        cold = ready()
        assert len(cold["resources"]) == 2, cold
        image = next(row for row in cold["resources"] if row["name"].endswith(".img"))
        wasm = next(row for row in cold["resources"] if row["name"].endswith(".wasm"))
        assert image["decoded"] == 64 * 1024 * 1024, image
        assert 0 < image["encoded"] < image["decoded"] / 2, image
        assert 0 < wasm["encoded"] < wasm["decoded"] / 2, wasm
        assert wasm["start"] < image["end"] and image["start"] < wasm["end"], cold
        assert all(row["value"] == 1 for row in cold["phases"]), cold
        assert page.locator("#boot-cover").is_visible()
        assert "around 10 seconds" in page.locator("#boot-estimate").inner_text()
        page.locator("#boot-details").click()
        assert page.locator("#boot-cover").is_hidden()
        assert page.locator("#screen").evaluate("screen => !screen.inert")
        assert page.locator("#boot-details").get_attribute("aria-expanded") == "true"
        page.screenshot(path=str(out / "boot-details.png"))
        page.locator("#boot-details").click()
        assert page.locator("#boot-cover").is_visible()
        assert page.locator("#screen").evaluate("screen => screen.inert")
        assert page.locator("#startup").is_hidden()
        assert page.locator("#keyboard-guide").is_visible()
        page.screenshot(path=str(out / "ready.png"))

        network.send("Network.emulateNetworkConditions", {
            "offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1,
        })
        page.reload()  # One emulator tab; dispose its workers before starting again.
        page.evaluate("""async () => {
            const { Qmp } = await import('./qmp.js');
            const command = Qmp.prototype.command;
            Qmp.prototype.command = function(...args) {
                window.testQmp = this;
                return command.apply(this, args);
            };
        }""")
        warm = ready()
        assert len(warm["resources"]) == 2, warm
        # Browsers may decline to retain the large image in their HTTP cache.
        warm_wasm = next(row for row in warm["resources"] if row["name"].endswith(".wasm"))
        assert warm_wasm["transferred"] < 1024, warm
        # A boot-time hint must never act as a countdown or reveal an unready guest.
        page.evaluate("window.testQmp.command('stop')")
        page.wait_for_function("parseInt(document.querySelector('#boot-elapsed').textContent) >= 12", timeout=20000)
        assert page.locator("#boot-cover").is_visible()
        assert page.locator("#screen").get_attribute("data-ready") == "false"
        page.screenshot(path=str(out / "waiting-past-estimate.png"))
        page.evaluate("window.testQmp.command('cont')")
        page.wait_for_function("""() => document.querySelector('#screen').dataset.ready === 'true'
            || document.querySelector('#status').textContent.startsWith('Stopped:')""", timeout=180000)
        assert page.locator("#screen").get_attribute("data-ready") == "true", page.locator("#status").inner_text()
        assert page.locator("#boot-cover").is_hidden()
        assert page.locator("#boot-controls").is_hidden()
        assert page.locator("#keyboard-prompt").is_visible()
        elapsed = page.locator("#boot-elapsed").text_content()
        page.wait_for_timeout(1100)
        assert page.locator("#boot-elapsed").text_content() == elapsed
        kernel = page.evaluate("""async () => {
            const { readBootKernel } = await import('./disk.js');
            const image = new Uint8Array(await (await fetch('./assets/thunderden.img')).arrayBuffer());
            const kernel = readBootKernel(image);
            const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', kernel));
            return {bytes: kernel.length, sha256: [...digest].map(value => value.toString(16).padStart(2, '0')).join('')};
        }""")
        assert kernel == {"bytes": 13923328, "sha256": "05ceac2e85254bc00b8c0ff119e5cadc0f3efcac9b618979345f20c574c1edb7"}, kernel
        (out / "startup.json").write_text(json.dumps({"cold": cold, "warm": warm, "kernel": kernel}, indent=2))

        # Drop monitor responses to reproduce a control failure without crashing the VM.
        page.evaluate("""() => {
            const qmp = window.testQmp;
            const command = qmp.command.bind(qmp);
            qmp.command = (name, args) => {
                if (name === 'screendump') {
                    qmp.receive = () => {};
                    window.droppingResponses = true;
                }
                return command(name, args, name === 'screendump' ? 1000 : 2000);
            };
        }""")
        page.wait_for_function("window.droppingResponses === true")
        page.locator("#screen").click()
        page.keyboard.press("ArrowDown")
        page.wait_for_function("document.querySelector('#status').textContent.startsWith('Stopped:')")
        first_error = page.locator("#boot-error").inner_text()
        assert first_error == "Emulator command timed out: screendump", first_error
        page.wait_for_timeout(2200)
        assert page.locator("#boot-error").inner_text() == first_error
        assert page.locator("#log").inner_text().count("Emulator command timed out:") == 1
        assert page.evaluate("window.testQmp.pending.size === 0 && window.testQmp.input.length === 0")
        assert page.locator("#screen").evaluate("screen => screen.inert")
        assert page.locator("#retry").is_visible()
        page.screenshot(path=str(out / "control-timeout.png"))

        for body, code, message, name in [
            ("invalid public image fixture", 200, "image checksum mismatch", "checksum"),
            ("missing public image fixture", 404, "Cannot load", "missing"),
        ]:
            page.route("**/assets/thunderden.img", lambda route: route.fulfill(
                status=code, body=body, content_type="application/octet-stream"))
            page.reload()
            page.wait_for_function("document.querySelector('#status').textContent.startsWith('Stopped:')")
            assert message in page.locator("#status").inner_text()
            if code == 404:
                assert page.locator("#startup-image").get_attribute("data-state") == "error"
            assert page.locator('#startup [data-state="active"]').count() == 0
            assert page.locator("#screen").get_attribute("data-frames") is None
            assert page.locator("#camera").is_disabled()
            assert not page.locator("#restart").is_disabled()
            assert page.locator("#boot-cover").is_visible()
            assert message in page.locator("#boot-error").inner_text()
            assert page.locator("#retry").is_visible()
            assert page.locator("#keyboard-guide").is_hidden()
            page.screenshot(path=str(out / f"error-{name}.png"))
            assert page.locator("#diagnostics").get_attribute("open") is not None
            page.locator("#boot-diagnostics").click()
            assert page.locator("#about-dialog").is_visible()
            assert message in page.locator("#log").inner_text()
            page.keyboard.press("Escape")
            assert page.locator("#about-dialog").is_hidden()
            page.unroute("**/assets/thunderden.img")
        # Manual raw-screen control remains available even without an automatic match.
        page.locator("#retry").click()
        page.wait_for_function("!document.querySelector('#boot-details').disabled", timeout=120000)
        page.locator("#boot-details").click()
        page.locator("#screen").click()
        page.keyboard.press("Escape")
        assert page.locator("#screen").get_attribute("data-ready") == "manual"
        assert page.locator("#boot-cover").is_hidden()
        assert page.locator("#boot-controls").is_hidden()
        assert page.locator("#screen").evaluate("screen => !screen.inert")
        assert not errors, errors
        print(json.dumps({"cold_resources": cold["resources"], "warm_resources": warm["resources"],
                          "phases": cold["phases"]}, indent=2), flush=True)
        print("PASS: visible progress, parallel HTTP-compressed downloads, cached Wasm and clear failures before guest startup")
        print("PASS: quiet cover, real-menu handoff, raw-screen toggle/takeover, elapsed timer beyond the hint and reduced motion")
        print("PASS: first control failure is preserved; pending commands are cancelled without replay")
    except Exception:
        page.screenshot(path=str(out / "failure.png"))
        print(json.dumps({"status": page.locator("#status").inner_text(), "errors": errors,
                          "diagnostics": page.locator("#log").inner_text()}, indent=2))
        raise
    finally:
        browser.close()
