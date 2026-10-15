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

Setup copies the generated emulator assets and downloads the original preview.8
image. Its SHA-256 is checked both during setup and in the browser before boot.
To reuse a previously downloaded release, run `npm run setup -- /path/to/thunderden.img`.

The emulator reserves about 2.3 GiB of Wasm memory; use one emulator tab at a time.
The tested Linux/Chromium machine reached the network chooser in about 23 seconds.
Other machines may take longer, particularly on the first startup.
The development server binds only to localhost and supplies the COOP/COEP headers
needed by the threaded emulator. No backend VM or native browser extension is used.

**Not yet connected:** real webcam capture. Browser recovery-word generation and
macOS/Safari/Firefox compatibility still require validation. Do not use this
prototype with real wallet material.

## Emulator integration

The custom emulator reuses 9elements' USB Video Class device and exposes a
host-side `frame-file` camera backend. The camera interface accepts complete
640×480 YUYV frames to the emulator's host filesystem. The emulated USB device
then delivers them to the existing Linux UVC driver inside Thunderden.

No helper, driver, scanner replacement, extra initramfs or application change is
inserted into the Thunderden guest. Its QR decoder and process isolation remain
the original implementations. This does **not** make a browser an airgapped device.

Current work is a development prototype, not a deployed or verified browser signer.
The native emulator has scanned a virtual USB webcam and verified a public fixture
address using the unchanged preview.8 release image. The Wasm binary builds and
starts with the USB camera and RNG device in Chromium. The page uses QEMU's own
QMP screen-dump and keyboard commands to present and control the original guest;
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
No recovery words are entered. Browser hosting requires HTTPS
(or localhost), and live camera capture will require explicit camera permission.
