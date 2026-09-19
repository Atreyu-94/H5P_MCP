// Shared budgets apply to raw input as well as normalized native parameters.
function limit(name, fallback) {
  const value = Number(process.env[`H5P_MCP_MAX_${name}`] || fallback);
  if (!Number.isSafeInteger(value) || value < 1) throw new Error(`Invalid limit ${name}`);
  return value;
}
function checkTree(root) {
  const stack = [[root, 0]];
  const seen = new WeakSet();
  const maxDepth = limit('DEPTH', 64), maxNodes = limit('NODES', 100000);
  let nodes = 0;
  while (stack.length) {
    const [value, depth] = stack.pop();
    if (++nodes > maxNodes) throw Object.assign(new Error('Input node budget exceeded'), {code:'INPUT_TOO_LARGE'});
    if (depth > maxDepth) throw Object.assign(new Error('Input nesting budget exceeded'), {code:'INPUT_TOO_DEEP'});
    if (value && typeof value === 'object') {
      if (seen.has(value)) throw Object.assign(new Error('Repeated or cyclic object'), {code:'INVALID_PARAMETER'});
      seen.add(value);
      const children = Object.values(value);
      if (nodes + stack.length + children.length > maxNodes) throw Object.assign(new Error('Input node budget exceeded'), {code:'INPUT_TOO_LARGE'});
      for (const child of children) stack.push([child, depth + 1]);
    }
  }
}
module.exports = {limit, checkTree};
