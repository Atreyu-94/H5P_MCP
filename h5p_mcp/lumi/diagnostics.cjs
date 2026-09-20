// Keep the legacy display path, but never parse it back into field identity.
const pointer = parts => parts.length ? '/' + parts.map(part => String(part).replace(/~/g, '~0').replace(/\//g, '~1')).join('/') : '';
const displayPath = parts => parts.map((part, index) => typeof part === 'number' ? `[${part}]` : `${index ? '.' : ''}${part}`).join('');
const diagnostic = (parts, message, code) => ({code, path:displayPath(parts), pointer:pointer(parts), message, retryable:false});
module.exports = {pointer, displayPath, diagnostic};
