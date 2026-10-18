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
| `browser-camera-access.py` | `ffmpeg`, `qrencode`, `tesseract` | On-demand access, timeout-safe waiting, guest cancellation and recoverable errors; requires a SeedQR-enabled release URL |
| `browser-camera-usb.py` | `tesseract` | Diagnostic: real guest errors after virtual USB unplug and whether replug restores QR/randomness capture, without injected Esc |
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
# For a separately prepared, unchanged SeedQR-enabled release bundle:
python3 tests/browser-camera-access.py test-results/camera-access --url http://127.0.0.1:4173/assets/seedqr-demo/index.html
python3 tests/browser-camera-usb.py test-results/camera-usb --url http://127.0.0.1:4173/assets/seedqr-demo/index.html
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

The emulator reports guest streaming requests through `VIDEO_STREAMING` QMP
events. If capture is off, the page pauses the VM and shows an in-screen prompt;
it does not call `getUserMedia()` until the user chooses **Enable camera**.
The VM remains paused through permission and camera startup, so waiting does not
consume the guest's camera timeout. **Cancel** resumes it and sends Esc to cancel
the guest operation. QMP accepts keyboard events only while the VM is running.
The prompt dims and blurs the current guest framebuffer, including genuine black
camera-startup screens. No preceding menu screenshot is substituted.

The webcam remains attached when browser capture is off. USB hotplug is not a
drop-in substitute for guest cancellation: the signer grants access to existing
camera device nodes before dropping root privileges; replacement nodes created
after replug do not inherit that setup. The USB diagnostic records native errors
and whether a tested image can reopen a replacement device. Cancelling through
Esc preserves the original device and its permissions. This depends on the guest
retaining Esc as its cancellation binding, not on menu text or numbering.

The `ready=/camera.ready` backend option separates capture readiness from image
content. The page writes byte `0` before stopping/clearing capture, and byte `1`
only after publishing a complete frame. Not-ready reads are normal underruns,
not backend failures. A black frame is valid video, not an error signal.
`VIDEO_FRAME` acknowledges the first complete frame handed to the emulated USB
camera; `VIDEO_ERROR` reports a backend read failure. Neither event proves that
the guest decoded a QR code. A missing initial delivery acknowledgment produces
a recoverable prompt rather than claiming the camera is absent.

Stopping browser capture releases the device, clears readiness and replaces the
host's latest frame with black. It also cancels an active guest camera step.
Frames already buffered in the emulator or guest may still arrive. Cancellation
of pending permission stops any stream granted later; browser permission dialogs
themselves cannot be dismissed by the page. Hiding the preview does not stop
capture. The illustrated webcam LED shows active browser capture, not guest use
or QR-decoding success. Permission, missing-device and busy/system errors are
best-effort browser classifications, not precise hardware diagnoses.

The emulator's Docker builder includes the Emscripten
[#26582](https://github.com/emscripten-core/emscripten/pull/26582) synchronous-proxy
lifetime correction. Rebuild both the builder and emulator, then rerun
`npm run setup` to pick up runtime changes. This correction is not proof that all
intermittent control stalls or browser background/resume cases are resolved.
See the [emulator guide](https://github.com/bitcoinerlab/thunderden-qemu-wasm/blob/master/THUNDERDEN.md)
for build commands and its standalone runtime smoke test.

## Image loading and boot

`web/release.js` pins the release URL, SHA-256, full byte size and `contentBytes`
(the byte after the last non-zero byte). Setup checks this loading-progress
metadata against the verified image. Both setup and the browser verify the whole
image. The browser then reads `/bzImage` from its FAT32 boot partition
without changing the image, and uses QEMU's `-kernel` option to boot it directly.
The root filesystem and applications are already built into that kernel; no
extra initramfs or separate kernel download is needed. The original image remains
attached as a read-only virtio disk. Direct boot skips GRUB and does not validate
the USB bootloader, UEFI or Secure Boot.

The kernel reader also supports the newer shared-kernel layout, where
`/EFI/BOOT/BOOTX64.EFI` is the EFI-stub Linux kernel used by both boot paths and
there is no separate `/bzImage`. It reads that original payload without changing
it. This compatibility does not change the default pinned preview.8 image.

The single-CPU profile disables ACPI and uses the kernel options:

```text
console=tty1 quiet loglevel=3 acpi=off random.trust_cpu=off random.trust_bootloader=off
```

The page covers quiet startup until the pinned release's public network-menu
title and completed footer appear in two consecutive emulator frames. Recognition
depends on the 640×480 VGA8x16 layout. It only reveals the original screen; it does
not render a replacement guest interface. **Show boot details** and manual control
remain available if recognition fails. The boot bar is explicitly estimated:
it follows elapsed time for the usual ten-second startup, then quietly becomes an
indeterminate activity indicator. The main card shows neither phase captions nor
an elapsed-seconds counter; the bar retains an accessible description of the
estimate and elapsed time. It never declares the guest ready because time elapsed.
Only actual ready-screen recognition completes the bar; manual takeover does not.
The estimate is not a deadline.

Changes to the pinned release need review of the checksum, byte sizes,
boot-kernel reader, menu markers and integration fixtures. Do not update the hash
alone or change the guest image to accommodate the demo.

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

The local server supplies `X-Uncompressed-Content-Length` for the original file
sizes, not compressed transfer sizes or estimates of time remaining. Total sizes
appear in the labels, with percentages beside the bars and no additional heading
spinner. The pinned image bar stays empty while connecting, rather than showing
an indeterminate sweep that resets when the response arrives. Image loading uses the
pinned `contentBytes` rather than the padded disk capacity as its progress target;
once reached, the last measured fill stays in place through the trailing empty
space and full checksum verification, without retracting or switching to
indeterminate activity. Image status text is limited to percentages, with
100% shown after verification; transient phase names and completion timings are
not rendered. Its percentage column keeps a fixed width and height to avoid
layout flicker. This changes the indicator only: no bytes are skipped, trimmed or
replaced. The image's full size remains visible in its label.

Emulator loading retains its right-hand phase/status text and **Ready** timing,
and uses its full decoded size. Without a known decoded size, it
stays indeterminate rather than inventing a percentage; its size can be shown
once the response completes. The Wasm module is compiled while downloading and
reused when initializing the emulator.

Use ETags or another consistent cache policy. Version assets together to avoid
mixing an old loader with a new Wasm binary or release image. Browsers may decline
to retain the large image in their cache. Verify startup, keyboard input, camera
permission and image verification on the deployed HTTPS origin before publishing.
