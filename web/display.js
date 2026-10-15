export function readPpm(bytes) {
  const header = new TextDecoder().decode(bytes.subarray(0, 64)).match(/^P6\n(\d+) (\d+)\n255\n/);
  if (!header) throw new Error('Invalid emulator screen format');
  const width = Number(header[1]);
  const height = Number(header[2]);
  if (width < 1 || height < 1 || width > 4096 || height > 4096 || bytes.length !== header[0].length + width * height * 3) {
    throw new Error('Invalid emulator screen dimensions');
  }
  return { width, height, rgb: bytes.subarray(header[0].length) };
}

const keys = {
  Enter: 'ret', Escape: 'esc', Space: 'spc', Backspace: 'backspace', Tab: 'tab',
  ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right',
  ShiftLeft: 'shift', ShiftRight: 'shift_r', ControlLeft: 'ctrl', ControlRight: 'ctrl_r',
  AltLeft: 'alt', AltRight: 'alt_r', MetaLeft: 'meta_l', MetaRight: 'meta_r',
  Minus: 'minus', Equal: 'equal', BracketLeft: 'bracket_left', BracketRight: 'bracket_right',
  Backslash: 'backslash', Semicolon: 'semicolon', Quote: 'apostrophe', Backquote: 'grave_accent',
  Comma: 'comma', Period: 'dot', Slash: 'slash', CapsLock: 'caps_lock',
  Delete: 'delete', Insert: 'insert', Home: 'home', End: 'end', PageUp: 'pgup', PageDown: 'pgdn',
};

export function qcode(code) {
  if (/^Key[A-Z]$/.test(code)) return code.slice(3).toLowerCase();
  if (/^Digit[0-9]$/.test(code)) return code.slice(5);
  if (/^F([1-9]|1[0-2])$/.test(code)) return code.toLowerCase();
  return keys[code];
}
