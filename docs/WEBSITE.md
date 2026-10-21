# Thunderden.com website direction

The first local website preview is available at `/site/`. It includes the branded
first screen, detail sections and a guided demo wallet at
`/site/wallet-mockup/`. It displays a paper-backup SeedQR, proposes a synthetic
payment and verifies the signed QR reply. This document also records the
remaining design direction.
The standalone demo baseline is preserved at `5aa029b`. The original demo remains
at `/`, alongside the website at `/site/`. Generated image and emulator bundles
remain separate from source control.

## First screen

Keep the simulator as the main experience, not a screenshot below a large
marketing banner. Keep these together near the top of the page:

- A compact header with the official logo and a visible GitHub link.
- A short introduction with each sentence on its own line, and a little breathing
  room before the demo label. Sentences wrap naturally on narrow screens.
- A centered demo label above both devices: "Try Thunder Den in your browser",
  set in small uppercase Inter with wider letter spacing and faint flanking
  lines. Follow it with "The real USB image, running locally on a virtual computer."
- The accepted laptop artwork and the working simulator.
- A small phone-companion QR panel to the left of the laptop, top-aligned with
  its outer frame.
- A small note below the laptop: "QR scanning and display are significantly
  better on a real laptop."

This is one scrolling home page, not a fixed-height hero or an attempt to fit
every explanation into one viewport. Cap the laptop's size and let the product
details follow naturally, visible alongside it on taller screens. Keep the
simulator readable rather than making it tiny to preserve the side panel.
Keep the full demo on usable computer and tablet layouts, including compact
laptop viewports such as 1024x600 and 1280x720. Below 1000px wide, the laptop
appears first with the companion card below it. Every visible demo starts
automatically, including on touch-only tablets.

At widths below 768px, or below 1000px with at most 500px height, show a
product-only homepage regardless of input device. Keep the introduction and
details, but show no laptop, QR panel, start button or demo-wallet button.
Instead, a quiet note says "Try it before preparing a USB drive" and "Open
thunderden.com on a computer to try the live browser demo. No USB drive needed."
The phone wallet remains available via the computer demo's QR and direct URL.

Fresh visits in these narrow layouts do not download or start the emulator.
Widening can start it normally. Resizing an existing guest hides/restores the
same guest rather than restarting; entering the narrow layout releases keyboard
input and cancels camera capture. Height alone never disables a full-width laptop.

Website download and boot bars are 14px high with rounded orange fills. Download
percentages sit beside their labels; a subtle sheen stays inside the measured
fill. Connecting and indeterminate waiting use a moving activity band instead.
Completed downloads show "✓ Ready" with a solid, still bar. Boot progress remains
an estimate and switches to activity after ten seconds, completing only on real
guest readiness. Reduced motion disables the effects. The standalone Preview 8
keeps its original loading presentation.

There is no toolbar, keyboard-help footer or warning strip below the laptop. The
initial in-screen prompt explains keyboard capture and release; screen-reader
status updates remain available. An enlarged power-button overlay matches the
existing laptop artwork, has a hover/focus "Restart demo" label and restarts
immediately without confirmation. Restart stops capture before reloading the
page and boots a fresh guest; it does not retain the demo session.

After keyboard capture, additional primary clicks on the guest display show a
small "Use your keyboard" reminder with arrow, Enter, Esc and number-key guidance.
It fades out after three seconds without another screen click or disappears
immediately on keyboard input, loss of focus or a click on the reminder itself.
Further screen clicks renew the timeout without blinking; there is no cooldown.
Clicking the reminder keeps keyboard capture and does not reopen it or inject
guest input. It never pauses the guest. The reminder stays within the display in
normal and expanded views and has no fade when reduced motion is requested. The
standalone Preview 8 is unchanged.

"Expand demo" sits just above the laptop frame, aligned with its right edge.
It opens an in-page view of the display rather than browser fullscreen or an
enlarged decorative keyboard. Its only header control is "Back to website", with
F8 as a keyboard exit even when the guest owns Tab. Esc continues to reach Thunder Den.
The same canvas, guest and camera stream remain active. Returning restores the
page position and focus. Other page controls are inert while expanded. Resizing
to a product-only narrow layout exits this view and cancels capture normally.

Camera controls live in the floating preview. "Hide preview" collapses the video
to a "Camera on" control with "Show" and "Stop camera" actions; it never removes
the ability to stop capture. Showing it again reuses the same camera stream.
Stopping releases capture and hides the panel. Both the preview indicator and
laptop LED represent actual browser capture. Technical diagnostics are available
from the in-screen error UI, not a permanent "About the demo" button.

### Introduction

**Turn an old laptop into a Bitcoin signer.**

Boot from USB without using the laptop's hard drive, Wi-Fi or Bluetooth.<br>
Review and sign transactions from your wallet app using QR codes.

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

The entry card says "Use your phone as a demo wallet" and "Scan this QR with your
phone to open a fake wallet web page. Use it with the virtual laptop to try
Thunder Den." Emphasize only "with your phone" to highlight the action. A short
"No app to install" note removes installation
ambiguity. No alternate-wallet link or developer-only preview notice appears in
the card. Avoid directional instructions that break when the layout stacks.
The entry QR contains only the companion URL, not recovery words or state.
Below it, "Or type this on your phone:" introduces the actual clickable wallet
address rather than an "Open the demo wallet" action. The displayed address and
QR use the same origin and route; do not display a different destination.

A compact phone/laptop illustration under the entry heading labels their roles
as "Demo wallet" and "Thunder Den". It contains no QR codes and is not repeated
inside the phone walkthrough. The ready prompt explains only keyboard capture,
release and navigation. Keep phone-wallet instructions outside the virtual laptop
so they do not compete with keyboard onboarding.

Keep the first version independent on each device. No account, pairing server
or background state synchronization is needed. Real QR codes cross between the
phone screen and laptop camera, then between the laptop screen and phone camera.
Both pages must clearly identify the experience as a demo.

### Guided flow

1. Show the public SeedQR on a torn notebook-paper sheet. Keep the next-step
   button directly below the paper and recovery words in a collapsed section
   below that. The QR and button fit together at small phone viewport sizes,
   including 375x547 and 320x460. Keep the compact "Demo wallet" header label
   without a separate warning paragraph or repeated label on the paper.
   Explain that the QR gives Thunder Den the demo recovery words, with a short
   QR-to-words explanation inside the collapsed section. Omit backup-storage
   advice from this demo flow. Give the exact network
   instruction, "1: Bitcoin mainnet", followed by "Scan a seed QR". After import,
   skip the passphrase. Advance only when the visitor chooses "I've scanned the seed QR".
2. Present a synthetic payment from the same fixture. Show its amount and fee,
   with the complete address beside "To". Keep the QR and scan-reply button
   visible together at the same compact phone sizes. Short UR fragments reduce
   QR density without changing the payment or hiding its review information.
3. Ask the visitor to review the transaction on the laptop before signing.
4. Let the phone scan the signed response and verify it locally. Report success
   only after checking the response, not just detecting a QR code.
5. Show "Signature verified" without an extra payment disclaimer. The fixed
   synthetic funding has no real coins and there is no broadcast feature.
6. Guide the visitor through ending the guest session. Do not claim that the phone
   can silently clear the laptop or guarantee physical memory erasure.
7. Suggest "Create a new wallet" after starting another session to explore entropy
   (randomness). Bitcoin Core randomness is always included; camera noise and
   either dice rolls or coin flips are optional additions. Clearly place the
   navigation steps on the virtual laptop. Keep the demo label visible. The
   phone's "Restart guide" button resets only the guide, never the guest session.

Start with the existing public fixtures where possible. Keep recovery words,
camera frames and transaction data out of URLs, logs and browser persistence.
The companion must not accept arbitrary recovery words or connect to real wallets.
Camera permission is requested only after an explicit action. Stop capture when
it is no longer needed.

Use decoded QR responses and explicit visitor actions to advance the guide.
Do not infer guest state from menu text, a guessed delay or black screen pixels.
Offer manual public-word entry for visitors without a second device.

## Details below the laptop

Lead with "Your hardware. Software you can inspect." Explain the purpose: an
offline signer uses secret keys to approve payments without going online. Keeping
keys off everyday connected devices reduces exposure to malware and online theft.
Hardware wallets are one approach. Thunder Den starts a visitor's laptop from USB instead of its
usual operating system. Introduce the USB as the carrier for the software before
discussing builds. Recovery words and keys are used in memory for the session;
the wallet app stays online while the laptop signs offline.

Follow with six short sections and links to the technical material:

1. **Bring your own laptop**: general-purpose hardware can predate the project.
   There is no Thunder Den hardware shipment, but existing hardware and firmware
   still need trust. Link reporting on the October 2026 Ledger reseller hardware
   implants through the generic "supply-chain attacks" link, without naming the
   vendor in the page copy or suggesting laptops are immune.
2. **Review the code with AI. Build it yourself.**: AI auditability is a design principle.
   Invite independent review, tests and builds from pinned sources. AI findings
   need verification; Linux, Bitcoin Core and build tools remain dependencies.
3. **A big screen. A real keyboard.**: comfortable transaction review and recovery
   input compared with a typical hardware wallet. Keep this to one short paragraph.
4. **Your wallet app. Your spending rules.**: Sparrow works directly; Liana uses
   the project's modified version and QR bridge. Mention support for many other
   wallets with QR-based air-gapped signing. Mention descriptor-based wallets,
   multisig and Miniscript policies, including time-delayed recovery. Keep setup
   details in the linked wallet guides without implying every wallet is compatible.
5. **A fresh session, every time**: one short paragraph on RAM-only wallet data,
   recovery input for each session and reusing or recreating the USB. Keep the
   recovery-word backup reminder. Omit scanner internals and standalone technical links.
6. **Take security further**: Secure Boot, a BIOS password and removal of
   storage/radio modules on suitable models. Keep the page's startup explanation
   short: boot only signed Thunder Den USB images and protect BIOS access with a
   password. Leave image signing, firmware terminology and setup details to the
   linked Secure Boot guide. Link a public laptop-disassembly example. Restricting
   boot to the intended signatures requires compatible firmware, only the intended
   trusted key and no legacy bypass. This checks software, not a particular USB stick.

Finish with the x86-64 Intel/AMD requirement, download/checksum steps and USB guide.
Keep the introduction concise and omit the standalone preview warning and Apple
Silicon aside. Explain relevant trust boundaries within the matching sections.
Keep GitHub easy to find in the header and footer. Describe Thunder Den as part of
the BitcoinerLAB family of open-source Bitcoin tools, linking the organization.

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
- The [Cloudflare preview](CLOUDFLARE.md) packages precompressed images below the
  25 MiB upload limit. A small Worker supplies ordinary HTTP content encoding.
  Local development still works independently with `npm start`.

## Local preview

The original demo at `/` and the existing labelled bundles remain available.
The website profile uses a separate verified copy of the published Preview 11
image, without changing the Preview 8 pin or guest bytes:

```sh
npm run setup:site
npm start
```

The website is pinned to the unsigned image from
[`v0.0.1-preview.11`](https://github.com/bitcoinerlab/thunderden/releases/tag/v0.0.1-preview.11),
with SHA-256 `e9c9e622ae3c129d85c636b8c2421e432130e78c063caadf61126931fb317242`.
Its bytes match the previously tested development image. It includes offscreen QR
rendering and steady captions. Browser checks covered actual signing and eight
seconds of animated replies: all 154 sampled frames decoded, without blank/white
redraw stages or caption changes. This does not guarantee tear-free rendering on
every framebuffer, browser or device. Physical two-device acceptance remains
separate. `setup:site` downloads the pinned release or accepts a matching local
image path as its optional argument.

Open `http://127.0.0.1:4173/site/`. The compatible emulator files must already be
installed as described in the development guide. Fonts and QR generation are
served locally, not from a third-party runtime service.

The viewport checks include 1280x800 and 1440x900, common scaled laptop sizes,
as well as 1280x640, 1024x600 and smaller browser windows. Short windows may need
vertical scrolling; the laptop and its controls remain in the page.

The entry QR follows the page's origin. A localhost address is not reachable from
a separate phone. This is a development constraint, not visitor-facing copy. Arrange
a phone-reachable preview address before testing across devices. Phone camera
scanning will also require HTTPS. The development server remains loopback-only;
use the separate Cloudflare preview workflow for physical two-device checks.

The companion uses locally bundled QR decoding, UR reconstruction and signature
verification. It requests the phone camera only after an explicit action and
releases capture after completion or cancellation, including late permission
grants. It has no recovery-word inputs, browser storage or transaction broadcast.

The full signing round trip has passed in Chromium on Linux: synthetic camera
MediaStreams feed the public SeedQR and unsigned payment into the unchanged guest,
then the phone scans actual guest pixels and verifies the signature. Real phones,
physical cameras and other mobile browsers remain unverified.

## Pending manual acceptance

- [ ] Test the live demo on a physical laptop with a webcam and a separate phone:
  entry QR/link, SeedQR import, transaction review, signing, phone verification
  and ending the guest session.
- [ ] Check the phone homepage and wallet walkthrough in mobile browsers.
- [ ] Test tablet startup, keyboard use and camera access before claiming tablet
  support.

The laptop layout is enabled for design review, not marked as hardware-verified.
Raise these checks again before declaring the demo ready or publishing it.
Automated viewport checks and synthetic camera tests do not complete this list.

## Suggested implementation order

1. Build the branded first-screen layout and readable detail sections. Verify
   common desktop sizes, narrow-screen behavior and unchanged simulator controls.
2. Test the implemented import/signing round trip on physical devices and mobile
   browsers. Animated QR reconstruction and actual guest signing are automated.
3. Test the guest's optional wallet-creation path; do not claim it is validated by
   the signing walkthrough.
4. Pin production artifacts and verify HTTPS hosting, compression, caching and
   shared-memory headers before launch. The Cloudflare workflow initially deploys
   the separately pinned website release for HTTPS testing, with search indexing
   disabled.
