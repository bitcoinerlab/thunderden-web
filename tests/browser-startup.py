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
    page.add_init_script("""document.addEventListener('DOMContentLoaded', () => {
        const row = document.querySelector('#startup-image');
        window.imageProgressSamples = [];
        window.imageProgressObserver = new MutationObserver(() => {
            const bar = row.querySelector('progress').getBoundingClientRect();
            if (bar.width) imageProgressSamples.push({text:row.querySelector('small').textContent,
                width:bar.width, height:row.getBoundingClientRect().height,
                determinate:row.querySelector('progress').hasAttribute('value'),
                value:row.querySelector('progress').value});
        });
        imageProgressObserver.observe(row, {attributes:true, childList:true, subtree:true, characterData:true});
    });""")
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
        assert page.locator('#boot-progress').is_hidden()
        assert page.locator("#keyboard-prompt").is_hidden()
        assert page.locator("#keyboard-guide").is_hidden()
        assert page.locator("#boot-cover #keyboard-instructions").count() == 0
        assert page.locator("#startup li").count() == 2
        assert page.locator("#startup summary").count() == 0
        assert page.locator("#screen").evaluate("screen => screen.inert")
        assert page.locator('.boot-spinner').count() == 0
        assert page.title() == 'Thunder Den Demo'
        assert page.locator('#boot-title').inner_text() == 'Loading Thunder Den…'
        assert page.locator('.boot-mark').count() == 0
        assert page.locator('#boot-message').is_hidden()
        assert page.locator('#startup-wasm label').inner_text().startswith('Browser x86-64 emulator')
        page.wait_for_function("""() => { const bar = document.querySelector('#image-progress');
            return bar.hasAttribute('value') && bar.value > .05 && bar.value < .95; }""", timeout=60000)
        progress = page.evaluate("""() => ({
            value: document.querySelector('#image-progress').value,
            detail: document.querySelector('#startup-image small').textContent,
        })""")
        assert page.locator('#startup-image label').inner_text() == 'Thunder Den image · 64 MiB'
        assert progress['detail'] == f"{int(progress['value'] * 100)}%", progress
        page.screenshot(path=str(out / "progress.png"))
        cold = ready()
        samples = page.evaluate('() => { imageProgressObserver.disconnect(); return imageProgressSamples; }')
        assert samples and all(not row['text'] or row['text'].removesuffix('%').isdigit() for row in samples), samples
        assert max(row['width'] for row in samples) - min(row['width'] for row in samples) < .5, samples
        assert max(row['height'] for row in samples) - min(row['height'] for row in samples) < .5, samples
        previous = 0
        for sample in samples:
            assert sample['determinate'], f'Image fill was reset to indeterminate: {sample}'
            assert sample['value'] >= previous, (previous, sample)
            previous = sample['value']
        assert len(cold["resources"]) == 2, cold
        image = next(row for row in cold["resources"] if row["name"].endswith(".img"))
        wasm = next(row for row in cold["resources"] if row["name"].endswith(".wasm"))
        assert image["decoded"] == 64 * 1024 * 1024, image
        assert 0 < image["encoded"] < image["decoded"] / 2, image
        assert 0 < wasm["encoded"] < wasm["decoded"] / 2, wasm
        assert wasm["start"] < image["end"] and image["start"] < wasm["end"], cold
        wasm_mib = round(wasm['decoded'] / 1024 / 1024, 1)
        assert page.locator('#startup-wasm .asset-size').inner_text().strip() == f'· {wasm_mib:g} MiB'
        assert all(row["value"] == 1 for row in cold["phases"]), cold
        assert next(row for row in cold['phases'] if row['id'] == 'startup-image')['detail'] == '100%', cold
        assert next(row for row in cold['phases'] if row['id'] == 'startup-wasm')['detail'].startswith('Ready · '), cold
        assert page.locator("#boot-cover").is_visible()
        assert page.locator('.boot-spinner').count() == 0
        assert page.locator('#boot-progress').is_visible()
        assert page.locator('#boot-progress').inner_text() == ''
        assert page.locator('#boot-progress-label').count() == 0
        assert page.locator('#boot-elapsed').count() == 0
        assert page.locator('#boot-progress-bar').evaluate('bar => bar.value < 1')
        assert page.locator('#boot-title').inner_text() == 'Booting Thunder Den…'
        assert page.locator('#boot-message').inner_text() == 'A real Linux system with Bitcoin Core’s cryptography, right in your browser.'
        assert page.locator('#boot-estimate').inner_text() == 'Usually around 10 seconds. Slower devices may take longer.'
        assert page.locator("#boot-estimate br").count() == 0
        page.locator("#boot-details").click()
        assert page.locator("#boot-cover").is_hidden()
        assert page.locator("#screen").evaluate("screen => !screen.inert")
        assert page.locator("#boot-details").get_attribute("aria-expanded") == "true"
        page.screenshot(path=str(out / "boot-details.png"))
        page.locator("#boot-details").click()
        assert page.locator("#boot-cover").is_visible()
        assert page.locator("#screen").evaluate("screen => screen.inert")
        assert page.locator("#startup").is_hidden()
        assert page.locator("#keyboard-guide").is_hidden()
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
        page.wait_for_function("Number(document.querySelector('#boot-progress-bar').getAttribute('aria-valuetext').match(/(\\d+) s elapsed/)[1]) >= 2", timeout=10000)
        assert page.locator('#boot-progress-bar').get_attribute('aria-valuetext').startswith('Estimated startup progress')
        assert page.locator('#boot-progress-bar').evaluate('bar => bar.hasAttribute("value") && bar.value > 0 && bar.value < 1')
        assert '%' not in page.locator('#boot-progress').inner_text()
        page.screenshot(path=str(out / 'estimated-boot.png'))
        page.wait_for_function("Number(document.querySelector('#boot-progress-bar').getAttribute('aria-valuetext').match(/(\\d+) s elapsed/)[1]) >= 12", timeout=20000)
        assert page.locator("#boot-cover").is_visible()
        assert page.locator("#screen").get_attribute("data-ready") == "false"
        assert page.locator('#boot-progress-bar').get_attribute('aria-valuetext').startswith('Still booting…')
        assert page.locator('#boot-progress').inner_text() == ''
        assert page.locator('#boot-progress-bar').evaluate('bar => !bar.hasAttribute("value")')
        page.screenshot(path=str(out / "waiting-past-estimate.png"))
        page.evaluate("window.testQmp.command('cont')")
        page.wait_for_function("""() => document.querySelector('#screen').dataset.ready === 'true'
            || document.querySelector('#status').textContent.startsWith('Stopped:')""", timeout=180000)
        assert page.locator("#screen").get_attribute("data-ready") == "true", page.locator("#status").inner_text()
        assert page.locator("#boot-cover").is_hidden()
        assert page.locator("#boot-controls").is_hidden()
        assert page.locator('#boot-progress-bar').evaluate('bar => bar.value === 1')
        assert page.locator('#boot-progress-bar').get_attribute('aria-valuetext') == 'Thunder Den is ready'
        assert page.locator("#keyboard-prompt").is_visible()
        assert "Click outside" in page.locator("#keyboard-prompt").inner_text()
        assert page.locator("#keyboard-prompt").evaluate("prompt => getComputedStyle(prompt).backdropFilter") == "blur(2px)"
        completed = page.locator('#boot-progress-bar').get_attribute('aria-valuetext')
        page.wait_for_timeout(1100)
        assert page.locator('#boot-progress-bar').get_attribute('aria-valuetext') == completed
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
        page.locator("#keyboard-prompt").click()
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
        assert page.locator('#boot-title').inner_text() == 'The demo stopped'
        assert page.locator('#boot-diagnostics').inner_text() == 'View details'
        assert page.locator('#boot-progress').is_hidden()
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
        assert page.locator('#boot-progress-bar').get_attribute('aria-valuetext') != 'Thunder Den is ready'
        assert page.locator("#boot-cover").is_hidden()
        assert page.locator("#boot-controls").is_hidden()
        assert page.locator("#screen").evaluate("screen => !screen.inert")
        assert not errors, errors
        print(json.dumps({"cold_resources": cold["resources"], "warm_resources": warm["resources"],
                          "phases": cold["phases"]}, indent=2), flush=True)
        print("PASS: visible progress, parallel HTTP-compressed downloads, cached Wasm and clear failures before guest startup")
        print("PASS: quiet spinner-free cover, real-menu handoff, raw-screen toggle/takeover and waiting beyond the time hint")
        print("PASS: first control failure is preserved; pending commands are cancelled without replay")
        print('PASS: total sizes stay in labels with percentage-only loading; estimated boot switches to activity after ten seconds and completes only on guest readiness')
        print('PASS: image progress stays determinate and never retracts, from connecting through complete verification')
    except Exception:
        page.screenshot(path=str(out / "failure.png"))
        print(json.dumps({"status": page.locator("#status").inner_text(), "errors": errors,
                          "diagnostics": page.locator("#log").inner_text()}, indent=2))
        raise
    finally:
        browser.close()
