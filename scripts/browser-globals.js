export { Buffer } from 'buffer';
export const process = { env: {}, nextTick: (callback, ...args) => queueMicrotask(() => callback(...args)) };
