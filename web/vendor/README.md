# QR generator

`qrcode-generator.js` is copied unchanged from the npm package
[`qrcode-generator@1.4.4`](https://www.npmjs.com/package/qrcode-generator/v/1.4.4).
The package archive was checked against its published SHA-512 integrity value.
The vendored file's SHA-256 is
`18ae399f81182bc9de916e9c77b195df20cc58d6f2d55a62b085a299f1bf1780`.

The MIT license is included in `qrcode-generator.LICENSE`, copied from upstream.
The website generates QR codes locally without an external QR service.

## Demo wallet bundle

`wallet.js` is built from `scripts/wallet-vendor.js` using the exact development
dependencies and integrity hashes in `package-lock.json`. It bundles BitcoinJS
PSBT parsing, noble-curves ECDSA verification, NGRAVE's bc-ur codec and jsQR camera
decoding. Buffer and minimal process compatibility stay scoped inside the module.
There are no external script or QR-service requests at runtime.

Run `npm ci` followed by `npm run build:wallet` to reproduce it. The build collects
the original licenses of all bundled packages, including nested dependency
versions, into `wallet.LICENSES.txt`.
