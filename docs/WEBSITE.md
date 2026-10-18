# Thunderden.com website direction

Draft for discussion, not an implemented website or a deployment promise.
The existing browser demo is preserved on `main` at `5aa029b`. Website work
starts on `feat/thunderden-com`. Generated image and emulator bundles remain
separate from source control.

## First screen

Keep the simulator as the main experience, not a screenshot below a large
marketing banner. On a normal desktop viewport, fit these together:

- A compact header with the official logo and a visible GitHub link.
- A short introduction with a "Learn the details" anchor.
- The accepted laptop artwork and the working simulator.
- A small phone-companion QR panel to the left of the laptop.
- A clear warning that the browser demo is not for real wallet material or funds.

The explanation sections start below the first screen. This is one scrolling
home page, not an attempt to fit every explanation into one viewport. Keep the
simulator readable rather than making it tiny to preserve the side panel.
On narrow screens, stack the content. Do not automatically start a multi-gigabyte
emulator on a phone; make the desktop requirement clear and offer the companion.

### Draft introduction

**Turn a spare laptop into an offline Bitcoin wallet.**

Thunder Den runs from USB without using the laptop's hard drive, Wi-Fi or
Bluetooth. Enter or scan your recovery words when you need them and exchange
transactions with your wallet app using QR codes.

Try the real software below with public demo data. **Learn the details**

Demo warning: "Demo only. Never enter real recovery words or use this demo for funds."

This describes the actual USB system. The surrounding browser demo is not an
air-gapped device. Avoid suggesting that a general-purpose laptop has the same
physical protections as a dedicated hardware wallet.

## Brand and writing

Follow [thunderden-brand](https://github.com/bitcoinerlab/thunderden-brand):

- Use the unchanged graphite horizontal logo on the light header.
- Use Inter with system sans-serif fallbacks. Self-host the font and its license;
  the brand repository does not include font files.
- Use warm white `#FAF9F6`, graphite `#222320` and restrained orange `#F7931A`.
- Copy only needed logos, icons and tokens into this repository.
- Keep the accepted hardware artwork. Do not redesign the guest interface.
- Use short sentences, everyday English and straight quotes. No Oxford commas.
- Explain unfamiliar terms before introducing abbreviations.
- Avoid absolute security claims or guarantees about erasing every trace of RAM.

## Phone companion

Public label: **Demo wallet**. Proposed route: `/wallet-mockup`.

The desktop QR should say "Try with your phone" and explain that scanning opens
a demo wallet which exchanges QR codes with the laptop. The entry QR contains
only the companion URL, not recovery words or wallet state.

Keep the first version independent on each device. No account, pairing server
or background state synchronization is needed. Real QR codes cross between the
phone screen and laptop camera, then between the laptop screen and phone camera.
Both pages must clearly identify the experience as a demo.

### Guided flow

1. Show a SeedQR for a fixed public recovery-word fixture. Explain how to select
   the matching network and scan it into Thunder Den.
2. Present a synthetic payment from the same fixture. Show its amount and fee,
   then display the unsigned transaction QR for Thunder Den to scan.
3. Ask the visitor to review the transaction on the laptop before signing.
4. Let the phone scan the signed response and verify it locally. Report success
   only after checking the response, not just detecting a QR code.
5. Explain that no payment was sent. There is no broadcast feature or live funds.
6. Guide the visitor through ending the guest session. Do not claim that the phone
   can silently clear the laptop or guarantee physical memory erasure.
7. Offer a separate exploration of wallet creation with camera input and optional
   coin tosses. Keep the browser-only warning visible and do not describe generated
   demo recovery words as safe for real funds.

Start with the existing public fixtures where possible. Keep recovery words,
camera frames and transaction data out of URLs, logs and browser persistence.
The companion must not accept arbitrary recovery words or connect to real wallets.
Camera permission is requested only after an explicit action. Stop capture when
it is no longer needed.

Use decoded QR responses and explicit visitor actions to advance the guide.
Do not infer guest state from menu text, a guessed delay or black screen pixels.
Offer manual public-word entry for visitors without a second device.

## Details below the laptop

Use short sections with optional links to GitHub for the technical material:

1. **How it works**: boot from USB, load recovery words, review on the laptop and
   exchange QR codes with a wallet app. Explain which device stays online.
2. **Nothing saved to the hard drive**: wallet state is kept in memory and the
   signer does not use internal storage or network adapters. Explain ending a session.
3. **Check before signing**: what the visitor reviews and why the laptop has its
   own display and approval controls.
4. **Secure Boot**: optional protection with a signed image and certificate setup
   on compatible UEFI hardware. It is not automatic on every laptop and the
   browser demo does not test it.
5. **Try it on a real laptop**: supported x86-64 hardware, image download,
   checksum verification and the USB guide. State the preview status and limits.

Keep GitHub easy to find in the header and footer. Do not hide essential product
limitations behind technical documentation or turn the page into an audit report.

## Hosting and preserved behavior

- Keep the original Preview 8 demo and its image unchanged. Choose an explicitly
  pinned SeedQR-capable release for the production experience, with its own profile.
  Do not present an uncommitted local guest build as a published release.
- Keep the accepted 640x400 pixelated display for the newer demo profile.
- Pin a matching emulator build with the required camera events. Its source stays
  in the separate emulator repository.
- Preserve whole-image verification, keyboard capture/release and explicit camera
  permission. No new helpers or replacement applications inside the guest image.
- Prefer static hosting with locally served assets. Do not add a backend just
  to coordinate the phone and laptop.
- Serve over HTTPS with the shared-memory headers required by the emulator.
  Include ordinary HTTP compression and validate decoded sizes and checksums.
- Cloudflare Pages has a [25 MiB per-file limit](https://developers.cloudflare.com/pages/platform/limits/).
  The unchanged image is 64 MiB. Test whether a precompressed HTTP representation
  can be delivered correctly within static-asset limits before selecting hosting.
  Do not assume that a header alone compresses an uncompressed file.
- [R2](https://developers.cloudflare.com/r2/pricing/) is an alternative for the
  image, with included free usage rather than unlimited free service.
  [Activation requires an R2 subscription](https://developers.cloudflare.com/r2/get-started/).
  Do not enable billing or deploy infrastructure without confirmation.

## Suggested implementation order

1. Build the branded first-screen layout and readable detail sections. Verify
   common desktop sizes, narrow-screen behavior and unchanged simulator controls.
2. Build the companion's fixed-fixture import and signing round trip. Test actual
   two-device camera use, animated QR formats and mobile browser support.
3. Add the optional wallet-creation guide with clear demo limits and cancellation.
4. Pin production artifacts and verify HTTPS hosting, compression, caching and
   shared-memory headers before launch. No DNS changes or publication yet.
