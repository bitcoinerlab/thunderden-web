# Cloudflare HTTPS preview

The preview uses Workers Static Assets and a small Worker for two disk images and
the Wasm binary. Each uploaded file must be below 25 MiB. The build stores gzip
representations: the current website image is about 13.6 MiB instead of 64 MiB.

The Worker returns these bytes with `Content-Encoding: gzip` and
`encodeBody: 'manual'`. Merely adding an encoding header in `_headers` caused
double compression in the local Cloudflare runtime. The browser performs ordinary
HTTP decompression; the existing loader verifies the complete original disk image.
No guest bytes are changed, trimmed or reconstructed. The Wasm MIME type and
decoded byte sizes are preserved, including for streaming compilation and progress.

Static requests are free and unlimited under Cloudflare's published pricing.
The three Worker-handled paths use the Workers Free daily allowance of 100,000
requests. No R2 bucket or paid subscription is required for this preview.

## Build and deploy

Prepare both images and the emulator using the usual setup instructions, then:

```sh
npm ci
npm run build:cloudflare
npm run preview:cloudflare
```

The build verifies both image pins and every emulator file against
`deploy/emulator.json`, checks lossless compression and enforces the upload limit.
Only the selected assets are packaged; local image archives and comparison
bundles are excluded. Generated output stays in ignored `dist/`.

Published routes are `/` for the website, `/wallet-mockup/` for the phone guide
and `/demo/` for the standalone Preview 8 demo. Local `npm start` routes are
unchanged. The old website paths redirect to the published routes.

Authorize Wrangler in your own browser, then deploy:

```sh
npx wrangler login --device
npm run deploy:cloudflare
npm run check:cloudflare -- https://your-preview.workers.dev
```

Use the deployment URL printed by Wrangler. Account identifiers and credentials
belong in Wrangler's local login configuration, not this repository. Domain
nameservers are assigned when the domain is added to Cloudflare; they are not
generic values or website IP addresses. A workers.dev preview does not require
changing the domain's nameservers.

`wrangler.jsonc` also declares `thunderden.com` as the custom domain. It requires
an active zone in the deploying account. Cloudflare manages its DNS record and
automatically issues and renews the HTTPS certificate. Remove any conflicting
old web-hosting A or CNAME record before attaching the domain. Certificate
provisioning can take longer than the routing update; verify HTTPS before testing
the browser demo. The phone link and QR follow the current origin, so the custom
domain uses `https://thunderden.com/wallet-mockup/`.

In the zone's **SSL/TLS > Edge Certificates** settings, enable **Always Use HTTPS**.
A valid certificate alone does not redirect HTTP visits. This setting ensures
visitors reach the secure origin required for camera access and shared memory.

The HTTP check verifies the HTTPS redirect on `thunderden.com`, decoded hashes,
MIME types, isolation headers, HEAD, ETag/304 revalidation and missing assets.
Then run the existing browser checks against the preview, for example:

```sh
python tests/browser-site.py test-results/cloudflare-layout --url https://your-preview.workers.dev/
python tests/browser-wallet.py test-results/cloudflare-signing --url https://your-preview.workers.dev/ --expanded --check-animation
```

All responses revalidate rather than treating mutable paths as immutable. The
deployment is uploaded together; do not deploy new loaders against old emulator
files. Compressed responses use `no-transform` to preserve their representation.

## Release and acceptance status

The initial deployed preview passed decoded-image and Wasm checksum checks,
shared-memory headers, cache revalidation, phone layouts and a full Chromium
signing round trip over HTTPS using synthetic camera streams. All 150 sampled
animated QR frames decoded, with 23 distinct payloads. These automated checks do
not verify physical cameras or mobile browsers.

The website uses the unchanged unsigned image from the published
`v0.0.1-preview.11` release, verified byte-for-byte against the previously tested
development image. It remains marked `noindex`. Complete the physical
laptop/phone checks in [WEBSITE.md](WEBSITE.md#pending-manual-acceptance) and test
mobile browsers before calling the demo ready. Remove the preview indexing rule
when launching the production website.

The custom domain also passed HTTPS, decoded-checksum, caching and shared-memory
checks after certificate provisioning completed. Chromium checks on that origin
covered real guest boot, public SeedQR import, keyboard isolation, resizing,
camera controls, expanded mode and restart. Camera input was synthetic.
