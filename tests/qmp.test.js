import assert from 'node:assert/strict';
import test from 'node:test';
import { Qmp } from '../web/qmp.js';

const bytes = text => new TextEncoder().encode(text);

test('QMP handles fragmented greeting and matching response IDs', async () => {
  const qmp = new Qmp();
  qmp.receive(bytes('{"QM'));
  qmp.receive(bytes('P":{"version":{}}}\r\n'));
  assert.deepEqual(await qmp.greeting, { version: {} });
  const first = qmp.command('first');
  const second = qmp.command('second');
  qmp.receive(bytes('{"event":"STOP"}\n{"return":"second result","id":2}\n'));
  qmp.receive(bytes('{"return":"first result","id":1}\n'));
  assert.equal(await first, 'first result');
  assert.equal(await second, 'second result');
  assert.equal(qmp.pending.size, 0);
});

test('terminal input wakes readers and produces complete QMP commands', async () => {
  const qmp = new Qmp();
  let wakes = 0;
  const subscription = qmp.pty.onReadable(() => { wakes++; });
  const result = qmp.command('cont');
  assert.equal(wakes, 1);
  assert.equal(qmp.pty.readable, true);
  const sent = JSON.parse(new TextDecoder().decode(qmp.pty.read(4096)));
  assert.deepEqual(sent, { execute: 'cont', arguments: {}, id: 1 });
  assert.equal(qmp.pty.readable, false);
  subscription.dispose();
  qmp.receive(bytes('{"return":{},"id":1}\n'));
  await result;
});

test('surface QMP errors and timeouts rather than hanging the page', async () => {
  const qmp = new Qmp();
  const error = qmp.command('invalid');
  qmp.receive(bytes('{"error":{"desc":"unknown command"},"id":1}\n'));
  await assert.rejects(error, /unknown command/);
  await assert.rejects(qmp.command('missing', {}, 5), /timed out/);
  assert.equal(qmp.pending.size, 0);
});

test('preserve a trailing emulator diagnostic without a newline', () => {
  const log = [];
  const qmp = new Qmp(line => log.push(line));
  qmp.receive(bytes('Emulator stopped before completing a line'));
  assert.deepEqual(log, []);
  qmp.flush();
  qmp.flush();
  assert.deepEqual(log, ['Emulator stopped before completing a line']);
});

test('wake a reader that subscribes after a command is already queued', async () => {
  const qmp = new Qmp();
  // The worker can check readability before this command, then subscribe later.
  const result = qmp.command('query-status');
  let wakes = 0;
  const subscription = qmp.pty.onReadable(() => { wakes++; });
  const sent = JSON.parse(new TextDecoder().decode(qmp.pty.read(4096)));
  qmp.receive(bytes(JSON.stringify({ return: {}, id: sent.id }) + '\n'));
  await result;
  subscription.dispose();
  assert.equal(wakes, 1);
});

test('closing QMP rejects pending commands and discards queued input without replay', async () => {
  const qmp = new Qmp();
  const first = qmp.command('screendump');
  const second = qmp.command('input-send-event');
  const error = new Error('Emulator command timed out: screendump');
  const firstRejected = assert.rejects(first, actual => actual === error);
  const secondRejected = assert.rejects(second, actual => actual === error);
  qmp.close(error);
  await Promise.all([firstRejected, secondRejected]);
  assert.equal(qmp.pending.size, 0);
  assert.equal(qmp.pty.readable, false);
  assert.deepEqual(qmp.pty.read(4096), new Uint8Array());
  const sequence = qmp.sequence;
  qmp.close(new Error('Later failure'));
  await assert.rejects(qmp.command('input-send-event'), actual => actual === error);
  assert.equal(qmp.sequence, sequence);
  qmp.receive(bytes('{"return":{},"id":1}\n')); // A late reply must not reopen it.
  assert.equal(qmp.pty.readable, false);
});
