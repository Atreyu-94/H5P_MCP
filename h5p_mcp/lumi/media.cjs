const fs = require('node:fs/promises');
async function readBounded(filename, maximum) {
  const file = await fs.open(filename, 'r');
  try {
    const chunks = [];
    let total = 0;
    while (true) {
      const buffer = Buffer.alloc(Math.min(65536, maximum + 1 - total));
      const {bytesRead} = await file.read(buffer);
      if (!bytesRead) break;
      total += bytesRead;
      if (total > maximum) throw new Error('media byte budget exceeded');
      chunks.push(buffer.subarray(0, bytesRead));
    }
    return Buffer.concat(chunks);
  } finally { await file.close(); }
}
module.exports = {readBounded};
