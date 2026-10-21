# Thunder Den Web

**Explore Thunder Den in your browser, without preparing a USB drive.**

[Thunder Den](https://github.com/bitcoinerlab/thunderden) turns a spare laptop into
an offline Bitcoin signer: a computer that checks and signs transactions without
connecting to the internet. Normally, you start its small Linux system from a
USB drive.
It keeps recovery words and private keys on that computer, and uses QR codes to
exchange wallet information and transactions with another device.

This project puts a virtual version of that laptop inside a web page. It runs
Thunder Den's original software in a browser-based computer emulator, rather than
recreating its menus in JavaScript. You can explore the interface with your
keyboard and connect your camera to try QR scanning with
[public test data](tests/fixtures/README.md).
No browser extension or server-side virtual machine is needed.

**This is an experimental demo, not a wallet for real funds. Never enter real
recovery words or send funds to a wallet created in the demo.** Running the signer
in a browser does not make your computer air-gapped or give it the protection of
a separate offline device.

## Run locally

You need Docker to build the emulator, Node.js 22 or later to prepare and serve
the website, and a desktop Chrome or Chromium browser. Keep the two repositories
next to each other:

```sh
git clone https://github.com/bitcoinerlab/thunderden-qemu-wasm.git
git clone https://github.com/bitcoinerlab/thunderden-web.git
```

First, follow the [emulator build instructions](https://github.com/bitcoinerlab/thunderden-qemu-wasm/blob/master/THUNDERDEN.md#wasm-build).
Then start the website:

```sh
cd thunderden-web
npm run setup
npm start
```

Open **http://127.0.0.1:4173**. The virtual computer starts automatically.
The emulator reserves about **2.3 GiB of memory**, so use one demo tab at a time
and allow time for the initial download and startup.

Setup copies the emulator's generated files and downloads the pinned, unchanged
`v0.0.1-preview.8` release image. It checks the image's SHA-256 checksum, and the
browser checks it again before booting. The demo does not automatically follow
newer Thunder Den releases. To reuse an existing copy of the pinned image:

```sh
npm run setup -- /path/to/thunderden.img
```

## Using the demo

Once Thunder Den's network menu appears, **click the screen** to give it keyboard
input. Use the arrow keys, Enter and Esc to navigate, and type normally when
asked. The screen has an orange outline while the keyboard is active. Click
outside the screen to release it. Keyboard mapping assumes a US layout.

When Thunder Den needs the camera, the page asks you to **Enable camera**.
Only that button requests browser permission. Images stay on your device, and
the virtual computer waits while you decide. **Cancel** cancels the camera step
inside Thunder Den, so you can use manual entry instead. Without a camera, you
can still enter public test recovery words, view public keys and display QR codes.

You can also enable the camera from the toolbar in advance. **Stop camera**
releases it and cancels any active camera step; **Hide preview** only hides the
preview and leaves capture running. Only use public test QR codes.

**Restart** discards the virtual computer and boots it again. **About** contains
background information and emulator diagnostics. During startup, **Show boot
details** reveals the original console and lets you take control if the page does
not recognize the ready screen. The illustrated laptop and USB drive are not
connections to physical hardware.

## How it works

The [companion emulator](https://github.com/bitcoinerlab/thunderden-qemu-wasm)
builds QEMU, a computer emulator, as WebAssembly so it can run inside a browser.
The website displays its screen, forwards keyboard input, and feeds browser
camera frames to an emulated USB webcam. Thunder Den's existing camera driver
and QR reader handle those frames.

The release image stays unchanged and is attached read-only. To shorten startup,
the website boots the Linux kernel already inside the verified image directly.
No application, driver or helper is added to Thunder Den. This skips its normal
USB bootloader, GRUB, so the demo does **not** test UEFI or Secure Boot.

This repository contains the website, camera integration and browser tests.
Emulator source and build tools live in `thunderden-qemu-wasm`; generated binaries
and disk images are not committed here.

## Current limits

Automated checks cover startup, keyboard navigation, a static QR/address flow,
camera controls and one animated transaction QR fixture in **Chromium on Linux**.
Camera tests use synthetic video rather than a physical webcam. These checks do
not establish support for every camera, QR format or browser.

Recovery-word generation, including camera-based randomness, is not validated
end to end in this browser demo. In the pinned release, camera collection can
finish while its statistical checks exceed the release's time limit. Other
browsers, operating systems, mobile devices and touch input remain unverified.
Performance depends on the visitor's hardware and browser; the configured camera
frame rate is a target, not a delivery guarantee.

See the [native Thunder Den project](https://github.com/bitcoinerlab/thunderden)
to learn about the actual USB signer, its design and its own validation status.

## Development and hosting

The experimental website is at **https://thunderden.com/**, with the original
Preview 8 demo at `/demo/`. For the local website profile, run `npm run setup:site`
to download the separately pinned, unchanged **Preview 12** image, then open
**http://127.0.0.1:4173/site/** after `npm start`. The original local demo stays at
`/`. See [the website notes](docs/WEBSITE.md) for the companion's current scope
and pending physical-device checks.

Install the pinned development dependencies to run all JavaScript unit tests:

```sh
npm ci
npm test
```

The phone walkthrough uses a checked-in browser bundle, not a runtime CDN.
After changing its vendor entry point, run `npm run build:wallet`. To reproduce
its public mainnet-format fixture, run `npm run fixture:wallet`.

See the [development guide](docs/DEVELOPMENT.md) for browser test commands,
integration details and static-host requirements. The
[Cloudflare guide](docs/CLOUDFLARE.md) covers building and deploying an HTTPS preview.
Hosting needs HTTPS, the shared-memory headers used by the emulator and HTTP
compression for the large downloads. The included Node server is for local
development, not a production hosting service.

Reports and contributions are welcome, especially reproducible browser or camera
issues. Use only public fixtures and remove private information from logs and
screenshots before sharing them.
