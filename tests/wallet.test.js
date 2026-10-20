import assert from 'node:assert/strict';
import test from 'node:test';
import { Psbt } from 'bitcoinjs-lib';
import { FIXTURE } from '../web/site/wallet-mockup/fixture.js';
import { fixture, signedFixture } from '../scripts/wallet-fixture.mjs';
import { paymentFrames, SignedReply, verifyReply } from '../web/site/wallet-mockup/exchange.js';
import { Buffer as BrowserBuffer, UR, UREncoder } from '../web/vendor/wallet.js';

test('the checked-in mainnet fixture is reproducible and contains only public demo data', () => {
  assert.deepEqual(FIXTURE, fixture);
  assert.equal(FIXTURE.network, 'Bitcoin mainnet');
  assert.match(FIXTURE.address, /^bc1/);
});

test('the original unsigned payment must not be accepted as a signed response', () => {
  assert.throws(() => verifyReply(Psbt.fromBase64(FIXTURE.psbt).toBuffer()), /Not signed/);
});

test('verify an actual signature against the fixed unsigned payment and known funding', () => {
  assert.equal(verifyReply(signedFixture().toBuffer()), true);
  const signed = signedFixture();
  // The verifier uses pinned funding metadata, not a responder-supplied value.
  signed.data.inputs[0].witnessUtxo = { script: new Uint8Array(), value: 1n };
  assert.equal(verifyReply(signed.toBuffer()), true);
});

test('reject a changed payment even with a valid signature for the changed transaction', () => {
  const changed = signedFixture(1);
  assert.throws(() => verifyReply(changed.toBuffer()), /does not match/);
});

test('reject corrupted signatures and non-ALL signature hash types', () => {
  for (const position of [10, -1]) {
    const signed = signedFixture();
    const signature = signed.data.inputs[0].partialSig[0].signature;
    signature[position < 0 ? signature.length - 1 : position] ^= 1;
    assert.throws(() => verifyReply(signed.toBuffer()), /Signature/);
  }
});

test('animated outgoing payment QR data reconstructs the exact unsigned PSBT', () => {
  const frames = paymentFrames();
  assert.ok(frames.length > 1);
  assert.ok(frames.every(frame => frame.length <= 120), 'Keep outgoing QR density suitable for small screens');
  const receiver = new SignedReply();
  assert.throws(() => { for (const frame of frames) receiver.receive(frame); }, /Not signed/);
});

test('multipart signed replies verify only after complete QR reconstruction, including out-of-order parts', () => {
  const wrapped = UR.fromBuffer(BrowserBuffer.from(signedFixture().toBuffer()));
  const encoder = new UREncoder(new UR(wrapped.cbor, 'crypto-psbt'), 100);
  const parts = Array.from({length:encoder.fragmentsLength}, () => encoder.nextPart().toUpperCase());
  const receiver = new SignedReply();
  for (const part of parts.slice(1).reverse()) assert.equal(receiver.receive(part).complete, false);
  assert.equal(receiver.receive(parts[0]).complete, true);
});

test('reject unrelated, malformed and excessive QR streams without success', () => {
  for (const frame of ['hello', FIXTURE.seedQr, 'ur:bytes/abcd', 'ur:crypto-psbt/1-999/abcd', 'ur:crypto-psbt/' + 'a'.repeat(7000)]) {
    assert.throws(() => new SignedReply().receive(frame));
  }
});
