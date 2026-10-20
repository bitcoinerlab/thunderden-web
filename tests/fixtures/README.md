# Public animated PSBT fixture

The phone walkthrough has its own smaller fixture in
`web/site/wallet-mockup/fixture.js`, reproduced by `npm run fixture:wallet`.
It uses the same public words with mainnet BIP84 account zero, one synthetic
100,000-sat funding output, a 20,000-sat payment, 79,000-sat change and a 1,000-sat
fee. The funding transaction has no live coins. The original multi-input fixture
below is preserved separately.

`animated-psbt.json` contains a 1,250-byte, seven-part `ur:crypto-psbt` stream.
Its fourteen frames include original fragments and fountain frames, replayed at
10 fps by the browser test. The unsigned PSBT's SHA-256 is recorded in the file.

All keys come from the public BIP39 `abandon`/`about` vector, using mainnet BIP84
account zero. Five synthetic funding transactions pay 100,000 sats each to
receiving indexes 0–4. The spend pays 200,000 sats to a witness program of twenty
`0x42` bytes, returns 299,000 sats to change index zero, and has a 1,000-sat fee.
The referenced funding transactions do not represent real coins. Never fund
these keys or use this fixture with real wallet material.

`animated-psbt.cpp` reproduces the JSON. It links against the native development
libraries from [Thunderden](https://github.com/bitcoinerlab/thunderden):
`libthunderden`, Bitcoin Core and `bc-ur`, like its `qr-command-runner` test target.
It is a host-side fixture producer only; it is never added to the release image.
The browser integration test consumes the checked-in JSON and does not need the
producer or a native Thunderden build.

## Public network-menu markers

`network-menu.json` records monochrome glyph masks for the unchanged preview.8
network-menu title and final footer, using the 640×480 VGA8x16 guest layout.
The masks test the browser boot-cover readiness detector; they contain no wallet
material and are never displayed as a replacement guest UI. The live detector
checks the emulator's original pixels, not a timer. Unknown layouts remain
accessible through **Show boot details** and manual raw-screen control.
