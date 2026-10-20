export { Psbt } from 'bitcoinjs-lib';
import { secp256k1 } from '@noble/curves/secp256k1.js';
export const verify = (hash, publicKey, signature) => secp256k1.verify(signature, hash, publicKey, { prehash: false, lowS: true });
export { Buffer } from 'buffer';
export { UR, UREncoder, URDecoder } from '@ngraveio/bc-ur';
export { default as decodeQr } from 'jsqr';
