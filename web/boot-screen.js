// Public network-menu title and final footer in the pinned 640×480 VGA8x16 UI.
// These pixel fingerprints only dismiss the browser's cover; no guest is modified.
const markers = [
  { x: 8, y: 48, width: 192, height: 16, hash: 1914411608 },
  { x: 8, y: 448, width: 280, height: 16, hash: 1824942286 },
];

export function isNetworkMenu({ width, height, rgb }) {
  if (width !== 640 || height !== 480) return false;
  return markers.every(marker => {
    let hash = 2166136261;
    for (let y = marker.y; y < marker.y + marker.height; y++) {
      for (let x = marker.x; x < marker.x + marker.width; x++) {
        const foreground = rgb[(y * width + x) * 3] > 64 ? 1 : 0;
        hash = Math.imul(hash ^ foreground, 16777619);
      }
    }
    return (hash >>> 0) === marker.hash;
  });
}
