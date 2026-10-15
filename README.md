# Thunderden Web

Experimental browser demo of [Thunderden](https://github.com/bitcoinerlab/thunderden),
using its **unmodified release image**. Never enter real recovery words or use
demo-generated wallets for funds.

The emulator source and build tools live in
[thunderden-qemu-wasm](https://github.com/bitcoinerlab/thunderden-qemu-wasm).
This repository owns the website, browser camera capture and integration tests.
Generated emulator binaries and disk images are not committed here.

## First milestone

The custom emulator reuses 9elements' USB Video Class device and exposes a
host-side `frame-file` camera backend. Browser capture publishes complete
640×480 YUYV frames to the emulator's host filesystem. The emulated USB device
then delivers them to the existing Linux UVC driver inside Thunderden.

No helper, driver, scanner replacement, extra initramfs or application change is
inserted into the Thunderden guest. Its QR decoder and process isolation remain
the original implementations. This does **not** make a browser an airgapped device.

Current work is a development prototype, not a deployed or verified browser signer.
The native emulator has scanned a virtual USB webcam and verified a public fixture
address using the unchanged preview.8 release image. A Wasm binary builds, but full
guest boot, display/input and live browser camera capture remain to be integrated.
See the emulator repository's `THUNDERDEN.md` for test commands and image hash.

## Development

Node.js 22 or later is sufficient for the camera conversion tests:

```sh
npm test
```

Browser hosting will require HTTPS (or localhost), camera permission and the
COOP/COEP headers required by the threaded emulator. Desktop Chrome is the initial
test target; macOS, Safari and Firefox support must be tested, not assumed.
