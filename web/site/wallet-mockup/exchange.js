import { Buffer, Psbt, UR, UREncoder, URDecoder, verify } from '../../vendor/wallet.js';
import { FIXTURE } from './fixture.js';

const equal = (a, b) => a.length === b.length && a.every((byte, index) => byte === b[index]);
const original = () => Psbt.fromBase64(FIXTURE.psbt);

export function paymentFrames() {
  const bytes = UR.fromBuffer(Buffer.from(original().toBuffer()));
  // Short fragments keep QR modules readable on compact phone screens.
  const encoder = new UREncoder(new UR(bytes.cbor, 'crypto-psbt'), 30);
  return Array.from({ length: encoder.fragmentsLength }, () => encoder.nextPart().toUpperCase());
}

export function verifyReply(bytes) {
  const reply = Psbt.fromBuffer(bytes);
  const expected = original();
  if (!equal(reply.data.globalMap.unsignedTx.toBuffer(), expected.data.globalMap.unsignedTx.toBuffer())) {
    throw new Error('This reply does not match the demo payment.');
  }
  for (let index = 0; index < expected.inputCount; index++) {
    const signatures = reply.data.inputs[index].partialSig;
    if (!signatures?.length) throw new Error('Not signed yet. Sign it in Thunder Den.');
    const publicKey = expected.data.inputs[index].bip32Derivation[0].pubkey;
    if (signatures.length !== 1 || !equal(signatures[0].pubkey, publicKey)
      || signatures[0].signature.at(-1) !== 1) {
      throw new Error('Signature does not match the demo wallet.');
    }
    // Copy only the signature. Prevouts, values, scripts and key paths stay pinned.
    expected.updateInput(index, { partialSig: signatures });
  }
  if (!expected.validateSignaturesOfAllInputs((key, hash, signature) => verify(hash, key, signature))) {
    throw new Error('Signature is not valid. Try scanning again.');
  }
  return true;
}

export class SignedReply {
  #decoder = new URDecoder();
  #frames = 0;

  receive(frame) {
    if (frame.length > 6000 || !/^ur:crypto-psbt\/(?:[1-9]\d{0,3}-[1-9]\d{0,2}\/)?[a-z]+$/i.test(frame)) {
      throw new Error('Scan the signed transaction QR from Thunder Den.');
    }
    const sequence = frame.match(/\/(\d+)-(\d+)\//);
    if (sequence && (Number(sequence[1]) > 4096 || Number(sequence[2]) > 64)) throw new Error('QR reply is too large.');
    if (++this.#frames > 512) throw new Error('Scan timed out. Try again.');
    this.#decoder.receivePart(frame);
    if (this.#decoder.isError()) throw new Error('Could not read the QR reply. Try again.');
    if (!this.#decoder.isComplete()) return { complete: false, progress: this.#decoder.estimatedPercentComplete() };
    const bytes = this.#decoder.resultUR().decodeCBOR();
    if (!(bytes instanceof Uint8Array) || bytes.length > 16384) throw new Error('Invalid transaction reply.');
    verifyReply(bytes);
    return { complete: true, progress: 1 };
  }
}
