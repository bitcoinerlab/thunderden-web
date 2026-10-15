// QMP controls the emulator itself. No agent or other code is added to the guest.
export class Qmp {
  constructor(onLog = () => {}) {
    this.input = [];
    this.readers = new Set();
    this.pending = new Map();
    this.sequence = 0;
    this.buffer = '';
    this.decoder = new TextDecoder();
    this.greeting = new Promise(resolve => { this.greet = resolve; });
    this.onLog = onLog;
    const self = this;
    this.pty = {
      get readable() { return self.input.length > 0; },
      writable: true,
      read: length => Uint8Array.from(this.input.splice(0, length)),
      write: bytes => this.receive(Uint8Array.from(bytes)),
      onReadable: fn => {
        this.readers.add(fn);
        return { dispose: () => this.readers.delete(fn) };
      },
      onSignal: () => ({ dispose() {} }),
      ioctl(command) {
        if (command === 'TIOCGWINSZ') return [24, 80];
        if (command === 'TCGETS') return { iflag: 0, oflag: 0, cflag: 0, lflag: 0, cc: new Uint8Array(32) };
      },
    };
  }

  receive(bytes) {
    this.buffer += this.decoder.decode(bytes, { stream: true });
    let end;
    while ((end = this.buffer.indexOf('\n')) !== -1) {
      const line = this.buffer.slice(0, end).trim();
      this.buffer = this.buffer.slice(end + 1);
      if (!line) continue;
      let message;
      try { message = JSON.parse(line); }
      catch { this.onLog(line); continue; }
      if (message.QMP) this.greet(message.QMP);
      const pending = this.pending.get(message.id);
      if (!pending) continue; // Greeting or asynchronous VM event.
      this.pending.delete(message.id);
      clearTimeout(pending.timer);
      if (message.error) pending.reject(new Error(message.error.desc));
      else pending.resolve(message.return);
    }
  }

  command(execute, args = {}, timeout = 30000) {
    const id = ++this.sequence;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Emulator command timed out: ${execute}`));
      }, timeout);
      this.pending.set(id, { resolve, reject, timer });
      const line = JSON.stringify({ execute, arguments: args, id }) + '\n';
      this.input.push(...new TextEncoder().encode(line));
      for (const reader of [...this.readers]) reader();
    });
  }
}
