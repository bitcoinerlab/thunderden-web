// Public network-menu title and final footer in the two pinned VGA8x16 profiles.
// These pixel fingerprints only dismiss the browser's cover; no guest is modified.
const markers = [
  { x: 8, y: 48, width: 192, height: 16, hash: 1914411608 },
  { x: 8, bottom: 32, width: 280, height: 16, hash: 1824942286 },
];

export function isNetworkMenu({ width, height, rgb }, expectedHeight = 480) {
  if (width !== 640 || height !== expectedHeight || ![400, 480].includes(expectedHeight)) return false;
  return markers.every(marker => {
    let hash = 2166136261;
    const top = marker.y ?? height - marker.bottom;
    for (let y = top; y < top + marker.height; y++) {
      for (let x = marker.x; x < marker.x + marker.width; x++) {
        const foreground = rgb[(y * width + x) * 3] > 64 ? 1 : 0;
        hash = Math.imul(hash ^ foreground, 16777619);
      }
    }
    return (hash >>> 0) === marker.hash;
  });
}
