export function renderQr(container, value, label) {
  const code = globalThis.qrcode(0, 'M');
  code.addData(value, /^\d+$/.test(value) ? 'Numeric' : /^[0-9A-Z $%*+./:-]+$/.test(value) ? 'Alphanumeric' : 'Byte');
  code.make();
  // The SVG contains generated module coordinates, not interpolated URL markup.
  container.innerHTML = code.createSvgTag({ cellSize: 4, margin: 16, scalable: true });
  const svg = container.querySelector('svg');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', label);
}
