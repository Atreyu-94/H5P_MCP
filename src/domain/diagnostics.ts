import type {Pointer} from './types.js';
// Keep the legacy display path, but never parse it back into field identity.
export const pointer = (parts: Pointer) => parts.length ? '/' + parts.map(part => String(part).replace(/~/g, '~0').replace(/\//g, '~1')).join('/') : '';
export const displayPath = (parts: Pointer) => parts.map((part, index) => typeof part === 'number' ? `[${part}]` : `${index ? '.' : ''}${part}`).join('');
export const diagnostic = (parts: Pointer, message: string, code: string) => ({code, path:displayPath(parts), pointer:pointer(parts), message, retryable:false});
