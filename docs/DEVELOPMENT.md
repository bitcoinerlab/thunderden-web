# Development guide

Start with the [README](../README.md) to build the emulator, prepare the website
and run the local server. This guide covers the integration and its tests.
Never use real recovery words, wallet files or personal camera recordings as
test data.

## Unit tests

```sh
npm test
```

These use Node.js's built-in test runner, with no npm dependencies. They cover
camera conversion and complete-frame publication, display parsing, keyboard
mapping, QEMU monitor commands, HTTP serving, download progress, image verification,
kernel extraction and ready-screen recognition. They do not boot Thunder Den.

## Browser tests

Run `npm start` in another terminal. Browser scripts default to
`http://127.0.0.1:4173`; use `--url` to test another address. Each script takes an
output directory for generated screenshots and diagnostics. Keep those outputs
outside source control, for example under the ignored `test-results/` directory.

All browser scripts need Python Playwright and Chromium. Install the Python
packages in a virtual environment. Playwright can install its own Chromium with
`python3 -m playwright install chromium`, or you can pass
`--chromium /path/to/chromium` to use an existing installation.

| Check | Additional tools | What it covers |
| --- | --- | --- |
| `browser-layout.py` | None | Loading UI, screen fit and illustration layout across viewport sizes |
| `browser-startup.py` | None | Compressed downloads, progress, caching, boot cover and error handling |
| `browser-boot.py` | `tesseract` | Actual guest boot, menu navigation and keyboard focus/release |
| `browser-camera.py` | `ffmpeg`, `qrencode`, `tesseract` | Static QR/address verification, permissions and camera lifecycle |
| `browser-animated-psbt.py` | Pillow, `qrencode`, `tesseract` | Animated transaction QR decoding and review; cancels without signing |
| `browser-camera-latency.py` | `tesseract` | Camera-frame age and complete frame changes using numbered video |
| `browser-camera-entropy.py` | `tesseract` | Synthetic camera collection and cancellation before word generation |

For example, run the non-camera checks with:

```sh
python3 tests/browser-layout.py test-results/layout
python3 tests/browser-startup.py test-results/startup
python3 tests/browser-boot.py test-results/boot
```

Run camera checks separately so only one emulator is active at a time:

```sh
python3 tests/browser-camera.py test-results/camera
python3 tests/browser-animated-psbt.py test-results/animated-psbt
python3 tests/browser-camera-latency.py test-results/camera-latency --seconds 120
python3 tests/browser-camera-entropy.py test-results/camera-collection
```

The camera scripts use Chromium's synthetic webcam through the real
`getUserMedia()` API, not a physical camera. Address and transaction checks use
the public BIP39 `abandon`/`about` fixture and synthetic coins. The animated
transaction test checks the expected payment, change and fee, then cancels.
See [fixture documentation](../tests/fixtures/README.md) for its source and scope.

The collection test checks delivery and cancellation, not entropy quality or
successful statistical assessment. Add `--wait-assessment` to wait for the
guest's reported outcome and check that emulator controls remain responsive.
A reported timeout or rejection is not a successful entropy assessment.

Optional performance budgets are available for suitable test systems:

- Boot: `--max-boot-seconds` and `--max-frame-interval-ms`.
- Camera latency: `--max-frame-age-ms` and `--max-p95-frame-age-ms`.
- Animated transaction QR: `--max-review-seconds`.

These measure different things. Faster screen refresh does not mean fresher
camera frames. The numbered-video counter repeats after 25.6 seconds, so longer
frame delays are ambiguous. Omit budgets for functional checks on slower systems.
Viewport emulation does not validate mobile browsers or touch input.

## Emulator integration

The website uses QEMU's monitor protocol (QMP) for screen dumps and keyboard
events. It requests one screen dump at a time and waits 33 ms after completion
before requesting another, avoiding a queue of stale screenshots. Terminal
failures preserve the first error, reject pending commands and discard queued
input; guest keystrokes are not retried or replayed.

The guest display is 640×480. The browser camera backend takes complete 320×240
YUYV frames at a target of 10 fps and presents them through a USB 2 EHCI controller.
EHCI is the tested browser configuration; xHCI guest scanning remains unresolved.
Target frame rates do not guarantee guest throughput or camera-frame freshness.

Stopping browser capture releases the device and replaces the host's latest
frame with black. Frames already buffered in the emulator or guest may still
arrive. Hiding the preview does not stop capture. The illustrated webcam LED
shows whether browser capture is active, not whether the guest is reading frames.

The emulator's Docker builder includes the Emscripten
[#26582](https://github.com/emscripten-core/emscripten/pull/26582) synchronous-proxy
lifetime correction. Rebuild both the builder and emulator, then rerun
`npm run setup` to pick up runtime changes. This correction is not proof that all
intermittent control stalls or browser background/resume cases are resolved.
See the [emulator guide](https://github.com/bitcoinerlab/thunderden-qemu-wasm/blob/master/THUNDERDEN.md)
for build commands and its standalone runtime smoke test.

## Image loading and boot

`web/release.js` pins the release URL and SHA-256. Both setup and the browser
verify the image. The browser then reads `/bzImage` from its FAT32 boot partition
without changing the image, and uses QEMU's `-kernel` option to boot it directly.
The root filesystem and applications are already built into that kernel; no
extra initramfs or separate kernel download is needed. The original image remains
attached as a read-only virtio disk. Direct boot skips GRUB and does not validate
the USB bootloader, UEFI or Secure Boot.

The single-CPU profile disables ACPI and uses the kernel options:

```text
console=tty1 quiet loglevel=3 acpi=off random.trust_cpu=off random.trust_bootloader=off
```

The page covers quiet startup until the pinned release's public network-menu
title and completed footer appear in two consecutive emulator frames. Recognition
depends on the 640×480 VGA8x16 layout. It only reveals the original screen; it does
not render a replacement guest interface. **Show boot details** and manual control
remain available if recognition fails. The displayed time hint is not a deadline.

Changes to the pinned release need review of the checksum, boot-kernel reader,
menu markers and integration fixtures. Do not update the hash alone or change the
guest image to accommodate the demo.

## Static hosting requirements

The deployed site serves static files; it does not run a server-side emulator.
It needs HTTPS for camera access and these response headers for shared memory:

```text
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

Serve `.wasm` as `application/wasm`. Keep assets on the same origin where possible;
cross-origin assets need compatible CORS/resource policies. Enable standard HTTP
gzip or Brotli for the `.img` and `.wasm` downloads. Verify image compression
explicitly: a host may not compress `application/octet-stream` by default. The
browser must receive the original decoded image bytes, not an application-level
archive or a modified image.

The local server supplies `X-Uncompressed-Content-Length` so progress can count
decoded bytes even with HTTP compression. This optional header is not the
compressed transfer size or an estimate of time remaining. Without a usable
decoded size, the page reports bytes loaded without inventing a percentage.
The zero-filled part of the disk image compresses well, so progress can move
quickly near the end. The Wasm module is compiled while downloading and reused
when initializing the emulator.

Use ETags or another consistent cache policy. Version assets together to avoid
mixing an old loader with a new Wasm binary or release image. Browsers may decline
to retain the large image in their cache. Verify startup, keyboard input, camera
permission and image verification on the deployed HTTPS origin before publishing.
