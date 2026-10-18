"""Check on-demand camera access using a SeedQR-enabled Thunder Den image.

Uses only the public abandon/about fixture and Chromium's synthetic webcam.
Browser failures are injected; stream requests and cancellation come from the
real guest. Requires Playwright, Chromium, qrencode, ffmpeg and tesseract.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from browser_screen import capture_guest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--url", required=True, help="Demo URL running a release with the Start a session menu")
parser.add_argument("--chromium")
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
origin = urlsplit(args.url)
origin = f"{origin.scheme}://{origin.netloc}"
subprocess.run(["qrencode", "-s", "10", "-m", "4", "-o", str(out / "seed.png"), "0000" * 11 + "0003"], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "10", "-i", str(out / "seed.png"),
                "-vf", "pad=640:480:(ow-iw)/2:(oh-ih)/2:color=white,format=yuv420p", "-frames:v", "10",
                "-f", "yuv4mpegpipe", str(out / "camera.y4m")], check=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=args.chromium, headless=True, args=[
        "--use-fake-device-for-media-stream", f"--use-file-for-fake-video-capture={out / 'camera.y4m'}"])
    context = browser.new_context(viewport={"width":1366,"height":768})
    context.grant_permissions(["camera"], origin=origin)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def expose_camera_fs(route):
        # Expose the host FS only in this test, to inject a real backend read error.
        response = route.fetch()
        source = response.text()
        assert source.count('emulator = module;') == 1
        route.fulfill(response=response, body=source.replace('emulator = module;', 'emulator = module; window.cameraFS = module.FS;'))

    context.route('**/app.js', expose_camera_fs)
    page.add_init_script("""(() => {
        const capture = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
        window.cameraMode = 'real'; window.cameraCalls = 0;
        navigator.mediaDevices.getUserMedia = constraints => {
            window.cameraCalls++;
            if (cameraMode === 'pending') return new Promise(resolve => {
                window.grantLate = () => capture(constraints).then(stream => {
                    window.lateTracks = stream.getTracks(); resolve(stream);
                });
            });
            if (cameraMode !== 'real') return Promise.reject(new DOMException('Synthetic camera failure', cameraMode));
            return capture(constraints);
        };
        const pixels = CanvasRenderingContext2D.prototype.getImageData;
        CanvasRenderingContext2D.prototype.getImageData = function(...args) {
            if (window.failCapture && this.canvas.id !== 'screen') throw new Error('Could not read the camera image. Try again.');
            const image = pixels.apply(this, args);
            if (window.blankFrames && this.canvas.id !== 'screen') {
                image.data.fill(0);
                for (let i=3; i<image.data.length; i+=4) image.data[i]=255;
            }
            return image;
        };
    })();""")

    def text():
        assert not errors, errors
        assert not page.locator("#status").inner_text().startswith("Stopped:")
        capture_guest(page, out / "screen.png")
        result = subprocess.run(["tesseract", str(out / "screen.png"), "stdout", "--psm", "11"], capture_output=True, text=True, check=True)
        return re.sub(r"\s+", " ", result.stdout).casefold()

    def wait(label):
        end = time.monotonic() + 60
        while time.monotonic() < end:
            if label.casefold() in text(): return
            page.wait_for_timeout(400)
        raise TimeoutError(label)

    def start():
        page.goto(args.url)
        starting = page.locator('#device').bounding_box()
        page.wait_for_function("document.querySelector('#screen').dataset.ready === 'true'", timeout=90000)
        loaded = page.locator('#device').bounding_box()
        assert all(abs(starting[field] - loaded[field]) < .5 for field in starting), (starting, loaded)
        page.evaluate("""async () => {
            const {Qmp} = await import('./qmp.js');
            const command = Qmp.prototype.command;
            Qmp.prototype.command = function(...args) { window.cameraQmp = this; return command.apply(this,args); };
        }""")
        page.locator("#keyboard-prompt").click()
        page.keyboard.press("4")
        wait("Start a session")
        page.evaluate("""() => {
            window.cameraEvents = [];
            const receive = cameraQmp.onEvent;
            cameraQmp.onEvent = event => {
                cameraEvents.push(event);
                if (!(window.dropFrameAck && event.event === 'VIDEO_FRAME')) receive(event);
            };
        }""")

    def camera_prompt():
        page.wait_for_function("!document.querySelector('#camera-request').hidden", timeout=15000)
        page.wait_for_function("cameraQmp.command('query-status').then(state => !state.running)")
        assert page.locator("#screen").evaluate("screen => screen.inert")
        copy = page.locator("#camera-request").inner_text()
        assert "Images stay on your device." in copy
        assert "microphone" not in copy and "Never enter real" not in copy
        frames = int(page.locator('#screen').get_attribute('data-frames'))
        page.wait_for_function("frames => Number(document.querySelector('#screen').dataset.frames) > frames", arg=frames)
        assert page.evaluate("""async () => {
            const {readPpm} = await import('./display.js');
            const {width,height,rgb} = readPpm(cameraFS.readFile('/screen.ppm'));
            const screen = document.querySelector('#screen');
            const rgba = screen.getContext('2d').getImageData(0,0,width,height).data;
            return screen.width===width && screen.height===height
                && rgb.every((value,index)=>value===rgba[Math.floor(index/3)*4+index%3]);
        }"""), 'Camera prompt must show the real guest framebuffer, not a saved menu'

    def scan():
        before = page.locator('#device').bounding_box()
        page.keyboard.press("1")
        camera_prompt()
        after = page.locator('#device').bounding_box()
        assert all(abs(before[field] - after[field]) < .5 for field in before), (before, after)

    def cancel():
        frames = int(page.locator('#screen').get_attribute('data-frames'))
        page.locator("#camera-cancel").click()
        page.wait_for_function("document.querySelector('#camera-request').hidden")
        page.wait_for_function("frames => Number(document.querySelector('#screen').dataset.frames) > frames", arg=frames)
        wait("Start a session")
        assert page.evaluate("cameraQmp.command('query-status').then(state => state.running)")
        assert page.locator("#camera-led").get_attribute("data-active") == "false"

    try:
        start()
        scan()
        assert page.evaluate("cameraCalls") == 0, "Guest access opened the browser permission prompt automatically"
        assert page.locator('#camera-request').evaluate('prompt => getComputedStyle(prompt).backdropFilter') == 'blur(2px)'
        page.screenshot(path=str(out / "camera-needed.png"))
        page.wait_for_timeout(12000)  # Longer than the guest's camera startup watchdog.
        assert page.evaluate("cameraQmp.command('query-status').then(state => !state.running)")
        assert not page.evaluate("cameraEvents.some(e => ['VIDEO_ERROR','VIDEO_FRAME'].includes(e.event))")
        cancel()
        print("PASS: real guest camera request opens contextual guidance; waiting does not run the VM; Cancel returns to manual entry", flush=True)

        scan()
        page.evaluate("cameraMode = 'pending'")
        page.locator("#camera-enable").click()
        page.wait_for_function("typeof grantLate === 'function'")
        cancel()
        page.evaluate("grantLate()")
        page.wait_for_function("window.lateTracks?.every(track => track.readyState === 'ended')")
        assert page.evaluate("document.querySelector('#camera-video').srcObject === null")
        print("PASS: cancelling pending permission stops a late-granted camera without turning it on", flush=True)

        scan()
        for mode, label in [("NotAllowedError", "permission denied"), ("NotFoundError", "No camera was found"), ("NotReadableError", "could not be opened")]:
            page.evaluate("mode => cameraMode = mode", mode)
            page.locator("#camera-enable").click()
            page.wait_for_function("label => document.querySelector('#camera-request-message').textContent.includes(label)", arg=label)
            assert page.locator("#camera-fallback").is_visible()
            assert page.locator("#camera-led").get_attribute("data-active") == "false"
            assert page.evaluate("cameraQmp.command('query-status').then(state => !state.running)")
        page.screenshot(path=str(out / "camera-error.png"))
        page.evaluate("cameraMode = 'real'; failCapture = true")
        page.locator("#camera-enable").click()
        page.wait_for_function("document.querySelector('#camera-request-message').textContent.includes('Could not read the camera image')")
        page.evaluate("failCapture = false")
        page.locator("#camera-enable").click()
        page.wait_for_function("document.querySelector('#camera-request').hidden")
        wait("Recovery words scanned")
        assert page.evaluate("cameraEvents.some(e => e.event === 'VIDEO_FRAME')"), "No complete-frame delivery acknowledgment"
        assert page.locator("#camera-led").get_attribute("data-active") == "true"
        capture_guest(page, out / "seed-qr-decoded.png")
        page.keyboard.press("Escape")
        wait("Start a session")
        page.evaluate("document.querySelector('#camera-video').srcObject.getVideoTracks()[0].dispatchEvent(new Event('ended'))")
        page.wait_for_function("document.querySelector('#camera-led').dataset.active === 'false'")
        assert page.locator("#camera-status").inner_text().startswith("Camera disconnected")
        page.evaluate("blankFrames = true; cameraEvents = []")
        scan()
        page.locator("#camera-enable").click()
        page.wait_for_function("document.querySelector('#camera-request').hidden && cameraEvents.some(e=>e.event==='VIDEO_FRAME')")
        page.wait_for_timeout(16000)  # A black image is valid video, not missing delivery.
        assert page.locator('#camera-request').is_hidden()
        assert page.locator('#camera').inner_text() == 'Stop camera'
        assert not page.evaluate("cameraEvents.some(e=>e.event==='VIDEO_ERROR')")
        page.locator("#camera").click()  # Stop must also cancel an active guest scan.
        wait("Start a session")
        assert page.locator("#camera-led").get_attribute("data-active") == "false"
        scan()
        page.evaluate("dropFrameAck = true")
        page.locator("#camera-enable").click()
        page.wait_for_function("document.querySelector('#camera-request-message').textContent.includes('is not confirmed') && !document.querySelector('#camera-request').hidden", timeout=22000)
        assert page.evaluate("cameraQmp.command('query-status').then(state => !state.running)")
        cancel()
        page.evaluate('dropFrameAck = false')
        scan()
        page.locator('#camera-enable').click()
        page.wait_for_function("document.querySelector('#camera-request').hidden")
        page.evaluate("cameraFS.writeFile('/camera.ready', Uint8Array.of(2))")
        page.wait_for_function("!document.querySelector('#camera-request').hidden && document.querySelector('#camera-request-message').textContent.includes('virtual camera could not deliver')")
        assert page.evaluate("cameraEvents.filter(e=>e.event==='VIDEO_ERROR').length") == 1
        cancel()

        # Streaming requests cover randomness collection too, not just QR scanning.
        calls = page.evaluate('cameraCalls')
        for key, expected in [('3', 'How many recovery words'), ('1', 'How your recovery words are created'),
                              ('Enter', 'Add randomness from your camera'), ('1', 'Add coin tosses or dice rolls'),
                              ('1', 'Collect camera randomness')]:
            page.keyboard.press(key)
            wait(expected)
        page.keyboard.press('Enter')
        camera_prompt()
        assert page.evaluate('cameraCalls') == calls
        cancel()
        assert not errors, errors
        (out / "events.json").write_text(json.dumps(page.evaluate("cameraEvents"), indent=2))
        print("PASS: blocked/missing/busy/capture failures recover; real UVC frames decode the public seed QR; disconnection stops capture", flush=True)
        print("PASS: Stop cancels an active guest scan; missing frame acknowledgment produces a recoverable delivery message", flush=True)
        print("PASS: black frames remain valid; real backend errors are reported once; camera-randomness permission can be cancelled without generation", flush=True)
        print("PASS: real boot and camera prompts keep laptop geometry stable; camera guidance shows the actual guest framebuffer", flush=True)
    except Exception:
        page.screenshot(path=str(out / "failure.png"))
        print(json.dumps({"status":page.locator("#status").inner_text(), "camera":page.locator("#camera-status").inner_text(), "errors":errors}, indent=2))
        raise
    finally:
        page.close()  # Dispose the VM before checking another browser capability.

    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.add_init_script("Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:undefined})")
    try:
        start()
        scan()
        assert page.locator("#camera-enable").is_hidden()
        assert "cannot provide camera access" in page.locator("#camera-request-message").inner_text()
        assert page.locator("#camera-fallback").is_visible()
        cancel()
        print("PASS: missing browser camera API gives a clear fallback; the simulator remains usable", flush=True)
    finally:
        browser.close()
