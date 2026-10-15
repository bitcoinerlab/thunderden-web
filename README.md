# Thunderden Web

Experimental browser demo of [Thunderden](https://github.com/bitcoinerlab/thunderden),
using its **unmodified release image**. Never enter real recovery words or use
demo-generated wallets for funds.

The emulator source and build tools live in
[thunderden-qemu-wasm](https://github.com/bitcoinerlab/thunderden-qemu-wasm).
This repository owns the website, browser camera capture and integration tests.
Generated emulator binaries and disk images are not committed here.

## Open the interactive prototype locally

Build the sibling [emulator repository](https://github.com/bitcoinerlab/thunderden-qemu-wasm/blob/master/THUNDERDEN.md#wasm-build)
first, keeping the two checkouts side by side. Then, with Node.js 22 or later:

```sh
npm run setup
npm start
```

Open **http://127.0.0.1:4173** in desktop Chrome/Chromium and click **Boot
Thunderden**. Click the screen to focus it, then use the arrows, Enter, Esc and
normal typing. Keyboard mapping currently assumes the guest's US layout.
**Restart / clear demo** reloads the page and discards the emulated computer.

For QR scanning, click **Enable camera** above the virtual screen and allow the
browser's camera request **before** starting a scan inside Thunderden. A small
local preview confirms which camera is active. Then use Thunderden's normal
**Scan a QR code** flow with public test recovery words. **Stop camera** releases
the device and replaces the latest host camera frame with black. Frames already
buffered by the emulator or guest may still be delivered. No microphone is requested.

Setup copies the generated emulator assets and downloads the original preview.8
image. Its SHA-256 is checked both during setup and in the browser before boot.
To reuse a previously downloaded release, run `npm run setup -- /path/to/thunderden.img`.

The emulator reserves about 2.3 GiB of Wasm memory; use one emulator tab at a time.
The tested Linux/Chromium machine reached the network chooser in about 23 seconds.
Other machines may take longer, particularly on the first startup.
The development server binds only to localhost and supplies the COOP/COEP headers
needed by the threaded emulator. No backend VM or native browser extension is used.

Physical webcam scanning, animated QR streams, browser recovery-word generation,
camera entropy/NIST timing, and macOS/Safari/Firefox compatibility still require
validation. Do not use this prototype with real wallet material.

Camera access requires HTTPS or localhost and permission from the browser and
operating system. If access is denied or the device is busy, check those
permissions, close other camera applications and retry. Video is processed locally
in the browser and is not uploaded.

## Emulator integration

The custom emulator reuses 9elements' USB Video Class device and exposes a
host-side `frame-file` camera backend. The camera interface accepts complete
320×240 YUYV frames to the emulator's host filesystem. The emulated USB device
then delivers them to the existing Linux UVC driver inside Thunderden.

No helper, driver, scanner replacement, extra initramfs or application change is
inserted into the Thunderden guest. Its QR decoder and process isolation remain
the original implementations. This does **not** make a browser an airgapped device.

Current work is a development prototype, not a deployed or verified browser signer.
Both native emulation and Chromium on Linux have scanned a virtual USB webcam and
verified a public fixture address using the unchanged preview.8 release image.
The browser check uses a synthetic webcam through the real `getUserMedia()` API,
not a physical camera. The website uses a virtual USB 2 EHCI controller; xHCI
registered correctly but the guest camera scanner timed out in Wasm.
The page uses QEMU's own QMP screen-dump and keyboard commands to present and
control the original guest;
there is no alternate UI or application injected inside the image. This initial
display path favors a small, inspectable prototype over high frame rates.
The image is attached as a read-only virtio boot disk. An IDE/snapshot configuration
stalled during browser startup, so it is not used by this prototype.
See the emulator repository's `THUNDERDEN.md` for test commands and image hash.

## Development

The unit tests need only Node.js; there are no npm dependencies:

```sh
npm test
```

An end-to-end boot/keyboard check is also available. It needs Python Playwright,
Chromium and `tesseract`, with the local server already running:

```sh
python3 tests/browser-boot.py /path/to/test-output --chromium /path/to/chromium
```

It reads the actual rendered guest screen and navigates menus through browser
keyboard events. On 2026-10-15 it passed the original release boot, selection of
Regtest, navigation into the public-key menu and Escape back to the main menu.
No recovery words are entered by this boot test. Browser hosting requires HTTPS
(or localhost), and live camera capture requires explicit camera permission.

The display requests one screenshot at a time, waiting 33 ms after completion
before requesting another. This replaces the initial 500 ms wait without queuing
old screenshots when the emulator is slow. The guest display is 640×480, enlarged
by the browser. The virtual camera's `browser` mode supplies 320×240 frames at
2 fps, while local browser capture continues at up to 10 fps. This trades camera
resolution and frame rate for fresh frames rather than a growing guest backlog.
Rebuild the emulator before using this mode; the original native `standard` mode
remains 640×480 at 10 fps.

In a Linux/Chromium comparison, display updates increased from about 1.9 to 21
per second and sampled menu key-to-screen latency fell from about 520 ms to
40 ms. A numbered synthetic camera showed about 0.5 seconds of frame age with
the browser profile, versus 7–8 seconds with the original profile. These are
measured prototype results, not cross-platform guarantees. Screen refresh rate
is not the same as fresh guest camera frames; the virtual camera is capped at
2 fps. Small or distant QR codes may need to fill more of the camera preview.

The boot check records display refresh intervals. To enforce a performance budget
on a suitable test machine, add `--max-frame-interval-ms 250`; omit that option for
functional testing on slower systems.

A separate camera test uses Chromium's fake webcam to show a known QR through
the real `getUserMedia()` and canvas APIs. It tests denied permission/retry, the
original image's UVC scanner and public fixture address verification, and camera
stop/restart/disconnection handling. It needs `ffmpeg` and `qrencode` in addition
to the boot-test tools:

```sh
python3 tests/browser-camera.py /path/to/camera-test-output --chromium /path/to/chromium
```

This camera test enters only the public `abandon`/`about` BIP39 fixture; it does
not access a physical webcam or use real wallet material.

To measure actual camera-frame age, rather than just screen refresh rate, use
the numbered-video check (Playwright, Chromium and `tesseract`; no physical camera):

```sh
python3 tests/browser-camera-latency.py /path/to/latency-output --chromium /path/to/chromium --seconds 120 --max-frame-age-ms 1000
```

It records frame age and complete frame changes, then cancels the original
scanner. The latency budget is optional and hardware-dependent. The synthetic
counter repeats after 25.6 seconds, so longer delays are ambiguous.
