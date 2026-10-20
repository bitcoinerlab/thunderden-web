// Generate public demo data only. Never used by the guest or a funded wallet.
import { pbkdf2Sync } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import { BIP32Factory } from 'bip32';
import * as ecc from '@bitcoinerlab/secp256k1';
import { Psbt, Transaction, payments, networks } from 'bitcoinjs-lib';

export const words = [...Array(11).fill('abandon'), 'about'].join(' ');
const root = BIP32Factory(ecc).fromSeed(pbkdf2Sync(words, 'mnemonic', 2048, 64, 'sha512'), networks.bitcoin);
const receivePath = "m/84'/0'/0'/0/0";
const changePath = "m/84'/0'/0'/1/0";
const receive = root.derivePath(receivePath);
const change = root.derivePath(changePath);
const funding = new Transaction();
funding.version = 2;
funding.addInput(new Uint8Array(32).fill(1), 0);
funding.addOutput(payments.p2wpkh({ pubkey: receive.publicKey }).output, 100000n);
const destination = payments.p2wpkh({ hash: new Uint8Array(20).fill(0x42), network: networks.bitcoin });
const psbt = new Psbt({ network: networks.bitcoin });
psbt.setVersion(2);
psbt.addInput({ hash: funding.getId(), index: 0, sequence: 0xfffffffd,
  nonWitnessUtxo: funding.toBuffer(),
  bip32Derivation: [{ masterFingerprint: root.fingerprint, path: receivePath, pubkey: receive.publicKey }],
});
psbt.addOutput({ address: destination.address, value: 20000n });
psbt.addOutput({ script: payments.p2wpkh({ pubkey: change.publicKey }).output, value: 79000n,
  bip32Derivation: [{ masterFingerprint: root.fingerprint, path: changePath, pubkey: change.publicKey }],
});
export const fixture = {
  network: 'Bitcoin mainnet',
  seedQr: '0000'.repeat(11) + '0003',
  words: words.split(' '),
  address: destination.address,
  paymentSats: 20000,
  feeSats: 1000,
  psbt: psbt.toBase64(),
};
export function signedFixture(locktime = 0) {
  const signed = psbt.clone();
  signed.setLocktime(locktime);
  signed.signInput(0, receive);
  return signed;
}
if (process.argv[1]?.endsWith('/wallet-fixture.mjs')) {
  await writeFile('web/site/wallet-mockup/fixture.js',
    '// Public abandon/about vector and synthetic funding. Never fund these keys.\n'
    + `export const FIXTURE = ${JSON.stringify(fixture, null, 2)};\n`);
  console.log('Generated the fixed mainnet-format demo payment with public test words.');
}
