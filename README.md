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

Open **http://127.0.0.1:4173** in desktop Chrome/Chromium. Loading and boot start
automatically inside the illustrated laptop screen. A prominent loading-time guide
explains the controls: click the screen to use the keyboard, then click outside it
to release it. An orange border appears immediately while the screen has focus,
and the footer shows the keyboard state. Boot and camera controls do not take
keyboard focus automatically. Once the guest is ready, an in-screen prompt stays
visible until the first keyboard activation; clicking the prompt or the screen
dismisses it. It does not return after releasing focus. Use the arrows, Enter, Esc
and normal typing; keyboard mapping currently assumes the guest's US layout.
**Restart** reloads the page, discards the emulated computer and boots again.

The original vector frame depicts a Thunderden-branded laptop with an attached
USB stick. It is illustrative, not physical USB passthrough. The scene
scales to keep the display and laptop visible on desktop viewports; narrow or short
viewports prioritize the display with a compact bezel. **About** holds background
information and diagnostics without pushing the screen down the page.

For QR scanning, click **Enable camera** above the virtual screen and allow the
browser's camera request **before** starting a scan inside Thunderden. A small
local preview confirms which camera is active. Then use Thunderden's normal
**Scan a QR code** flow with public test recovery words. **Stop camera** releases
the device and replaces the latest host camera frame with black. Frames already
buffered by the emulator or guest may still be delivered. No microphone is requested.
**Hide preview** closes only the preview panel, not the camera. The illustrated
webcam LED changes from red to green while browser capture is active, and returns
to red on stop or error. Automatic boot does not request camera access.

Setup copies the generated emulator assets and downloads the original preview.8
image. Its SHA-256 is checked both during setup and in the browser before boot.
To reuse a previously downloaded release, run `npm run setup -- /path/to/thunderden.img`.

The emulator reserves about 2.3 GiB of Wasm memory; use one emulator tab at a time.
The tested Linux/Chromium machine reached the network chooser in about 12–15 seconds
with direct kernel boot, versus about 25 seconds in the earlier GRUB boot check.
Other machines may take longer, particularly on the first startup.
The development server binds only to localhost and supplies the COOP/COEP headers
needed by the threaded emulator. No backend VM or native browser extension is used.

Broader physical-webcam and animated-QR coverage, browser recovery-word generation,
and macOS/Safari/Firefox compatibility still require validation. Camera entropy
is not working end to end: an isolated synthetic-video check completed collection
but NIST assessment exceeded the guest's 120-second limit. Sustained assessment
has also reproduced an intermittent emulator-control stall in a visible, focused
Chromium tab; passing collection/cancellation checks do not cover that longer flow.
One synthetic animated
UR PSBT fixture is covered below; that does not
establish compatibility with every animated QR format. Do not use real wallet material.

Camera access requires HTTPS or localhost and permission from the browser and
operating system. If access is denied or the device is busy, check those
permissions, close other camera applications and retry. Video is processed locally
in the browser and is not uploaded.

## Startup and downloads

The startup panel shows the image and Wasm download/compilation progress, alongside
keyboard instructions. Loader/firmware loading happens in parallel without separate
status rows. SHA-256 verification starts as soon as the image is loaded, while
Wasm compilation can continue in parallel. After verification, the existing
`/bzImage` is read from the image's FAT32 boot partition without changing it.
The compiled Wasm module is reused by
the emulator; it is not downloaded again during initialization.

Compression belongs to HTTP, not the application: `npm start` negotiates standard
gzip for the original `.img` and `.wasm` URLs, and the browser decompresses them
automatically. No custom archive or modified image is used. In a Linux/Chromium
check, the 64 MiB image transferred about 13.7 MiB and the 11.3 MiB Wasm file about
3.1 MiB. A different static host/CDN should enable gzip or Brotli for these files
and preserve the COOP/COEP headers required by the emulator.

File progress counts decoded bytes. The local server supplies the optional
`X-Uncompressed-Content-Length` header so compressed responses can show accurate
percentages. The counters explicitly label these as unpacked bytes, not transfer
percentages or time remaining. Much of the release image after its first roughly
16 MiB is zero-filled disk space: it compresses very well, so the unpacked-byte
bar can jump rapidly through the remaining 48 MiB near the end of the download.
If a host does not provide a usable decoded size, the bar shows
activity and bytes loaded instead of inventing a percentage. Compilation,
verification and emulator startup use the boot card's activity indicator, not
estimated percentages. The download panel disappears when browser preparation
finishes; no completed-stats accordion remains.

A browser-side boot card covers the quiet guest startup with a spinner, elapsed
time and an approximate "usually around 10 seconds" hint after file loading.
That hint is not a countdown or deadline. The original guest menu is revealed
only after its public title and completed footer are observed in two consecutive
emulator frames. The detector targets this pinned release's 640×480 VGA8x16
layout and stops after handoff. It does not draw a replacement guest screen.
**Show boot details** reveals the raw console; users can take control there if
recognition fails. Errors appear inside the display with restart and diagnostics
controls, instead of leaving an indefinite spinner. Diagnostics are also available
under **About**. Reduced-motion preferences disable
the decorative spinner animation.

### Direct kernel boot

The browser uses QEMU's `-kernel` option with the exact kernel extracted from the
verified release. Its built-in root filesystem and applications are unchanged;
there is no replacement kernel, guest helper, extra initramfs or separate kernel
download. **GRUB is bypassed.** This demo therefore does not validate the original
bootloader path, UEFI or Secure Boot.

The single-CPU demo disables ACPI firmware tables and passes `acpi=off` to avoid
expensive ACPI discovery under emulation. `console=tty1 quiet loglevel=3` keeps
Linux startup quiet behind the browser's boot card. The existing `random.trust_cpu=off` and
`random.trust_bootloader=off` settings are retained. The earlier blank interval
covered kernel decompression/initialization, root-filesystem unpacking and device
discovery; normal messages were hidden by the original `loglevel=3` boot setting.
There was no additional image download or fixed 20-second wait.

The browser still verifies the unchanged image before guest startup. The hash
check took tens of milliseconds in the tested Linux/Chromium run, not a second
download. HTTP ETags allow cached files to be revalidated without retransmitting
their bodies, but browsers may decline to retain the large image in their cache.

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
The original image remains attached read-only as a virtio disk; the emulator now
boots its extracted kernel directly. An earlier IDE/snapshot configuration stalled
during browser startup, so it is not used by this prototype.
See the emulator repository's `THUNDERDEN.md` for test commands and image hash.

## Development

The unit tests need only Node.js; there are no npm dependencies:

```sh
npm test
```

The startup check needs Python Playwright and Chromium, with the local development
server running. It checks progress on a throttled connection, overlapping HTTP-
compressed downloads, Wasm cache reuse, and checksum/missing-file failures before
guest startup. It also pauses the guest past the time hint to check that the cover
waits for actual readiness, tests the raw-screen toggle/takeover, and checks the
elapsed timer and reduced-motion behavior:

```sh
python3 tests/browser-startup.py /path/to/startup-output --chromium /path/to/chromium
```

The layout check holds downloads pending and checks automatic loading, in-screen
progress, display fit and desktop laptop fit across Chromium viewport sizes. This
is a layout check, not validation of mobile browsers or touch input:

```sh
python3 tests/browser-layout.py /path/to/layout-output --chromium /path/to/chromium
```

The QMP terminal bridge immediately wakes a newly subscribed reader if commands
are already queued. A unit test covers this readiness-check/subscription race,
which otherwise could leave the website waiting for an emulator response.
Terminal failures preserve the first error, reject outstanding commands and clear
queued input; the page never retries or replays guest keyboard commands.

The emulator's pinned Emscripten runtime includes the upstream
[#26582](https://github.com/emscripten-core/emscripten/pull/26582) synchronous-proxy
context-lifetime correction. Rebuild its Docker builder and emulator, then rerun
website setup to pick it up. This is a targeted control-stall candidate, not proof
that every intermittent hang or browser background/resume case is resolved.
The rebuilt emulator stayed responsive through a full synthetic assessment run
and a separate run with a controlled ten-second page suspension/resume. Both
reached the guest's unchanged assessment deadline and rejected camera data; neither
was a successful entropy assessment. Startup/error handling, boot/keyboard, static
QR, camera lifecycle and the public animated PSBT checks also passed in Chromium
on Linux. Actual background-tab policies on other browsers remain unverified.

An end-to-end boot/keyboard check is also available. It needs Python Playwright,
Chromium and `tesseract`, with the local server already running:

```sh
python3 tests/browser-boot.py /path/to/test-output --chromium /path/to/chromium
```

It checks that the boot cover hands off to the actual rendered guest network menu
and navigates menus through browser keyboard events. On 2026-10-15 it
passed direct boot of the original release kernel, selection of
Regtest, navigation into the public-key menu and Escape back to the main menu.
No recovery words are entered by this boot test. Browser hosting requires HTTPS
(or localhost), and live camera capture requires explicit camera permission.
OCR checks capture the original canvas pixels at a fixed 2× scale, independent of
the illustrated display's CSS size; layout screenshots check the fitted scene.

The display requests one screenshot at a time, waiting 33 ms after completion
before requesting another. This replaces the initial 500 ms wait without queuing
old screenshots when the emulator is slow. The guest display is 640×480, fitted
without cropping inside the illustrated laptop display. The virtual camera's `browser` mode supplies 320×240 frames at
10 fps, while local browser capture continues at up to 10 fps. This is a higher-rate
trial of the smaller-frame profile; guest CPU count and display size are unchanged.
Rebuild the emulator before using this mode; the original native `standard` mode
remains 640×480 at 10 fps.

The emulator now returns an empty isochronous USB transfer between scheduled
images, instead of an error-marked UVC header. Normal frame pacing must not mark
the next capture buffer as damaged. Actual backend read failures remain errors;
no guest checks are disabled.

Earlier Linux/Chromium checks with the 320×240/2 fps profile measured about
0.5 seconds of camera frame age. The original heavier display/camera setup
measured 7–8 seconds. Those configurations differed in more than frame rate,
so they do not establish a 2 fps browser limit. Screen refresh rate and fresh
guest camera frames are separate measurements. Small or distant QR codes may
need to fill more of the camera preview. These are prototype observations,
not cross-platform performance guarantees.

A controlled Linux/Chromium comparison kept the USB idle-transfer correction,
resolution, CPU count and display settings identical, changing only camera cadence.
One 60-second numbered-video sample per profile measured:

| Target cadence | Median frame age | p95 frame age | Complete frame changes/sec |
| --- | --- | --- | --- |
| 2 fps | 0.50 s | 0.69 s | 1.98 |
| 10 fps | 2.04 s | 2.24 s | 2.88 |

The 10 fps target was not achieved by the guest preview, and its frame age exceeded
the optional one-second median budget. This is a trial, not a demonstrated latency
improvement or a prediction of performance on other systems.

The boot check records display refresh intervals. To enforce a performance budget
on a suitable test machine, add `--max-frame-interval-ms 250`; omit that option for
functional testing on slower systems.
The optional `--max-boot-seconds` argument separately bounds the time from the
page load to observing the network chooser, including browser preparation.

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
Add `--max-p95-frame-age-ms 1000` to check the slow tail as well as the median.

An animated PSBT test replays a public, seven-part `ur:crypto-psbt` stream at
10 fps through the synthetic webcam, then checks the original guest's transaction
review for the expected payment, change and fee. It cancels without approving
signing. Requires Playwright, Pillow, Chromium, `qrencode` and `tesseract`:

```sh
python3 tests/browser-animated-psbt.py /path/to/animated-output --chromium /path/to/chromium
```

The fixture and host-side producer are described in `tests/fixtures/README.md`.
In one Linux/Chromium run per cadence with the same USB correction, this short
repeating fixture reached review in 8.1 seconds at 10 fps and 27.5 seconds at 2 fps.
Earlier 2 fps runs varied from roughly 20 seconds to over a minute. Completion time
depends on the animation and sampling phase; this is not a general scan-time guarantee.
The optional `--max-review-seconds` argument sets a hardware-dependent budget
measured from leaving the passphrase prompt to reaching transaction review.

The camera-collection check uses deterministic public synthetic noise and the
guest's native capture path. It waits for collection to finish and assessment to
start, then cancels without generating recovery words. It checks frame delivery,
not NIST completion, entropy quality or secure wallet generation:

```sh
python3 tests/browser-camera-entropy.py /path/to/collection-output --chromium /path/to/chromium
```

Add `--wait-assessment` to check emulator-control responsiveness until the guest
reports an assessment outcome. A guest-reported timeout is recorded as an
incomplete assessment, not a successful entropy check. The test never confirms
use of camera data or proceeds to recovery-word generation.
