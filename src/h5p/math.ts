import type {Native} from '../domain/types.js';
import {checkTree} from '../domain/limits.js';
// MathDisplay is an addon, not a runnable activity. Never download on export.
const MATH_LIBRARY = { machineName: 'H5P.MathDisplay', majorVersion: 1, minorVersion: 0 };

export function containsLatex(value: unknown): boolean {
  checkTree(value);
  const stack = [value];
  while (stack.length) {
    const current = stack.pop();
    if (typeof current === 'string' && /\\\(|\\\[|\$\$/.test(current)) return true;
    if (current && typeof current === 'object') stack.push(...Object.values(current));
  }
  return false;
}

export async function inspectMath(manager: Native, params: unknown): Promise<Native> {
  if (!containsLatex(params)) return { detected: false };
  try {
    const library = await manager.getLibrary(MATH_LIBRARY);
    return { detected: true, installed: true, library: 'H5P.MathDisplay 1.0', patch_version: library.patchVersion };
  } catch {
    return { detected: true, installed: false, library: 'H5P.MathDisplay 1.0',
      error: 'LaTeX requires H5P.MathDisplay 1.0. Install the official addon with h5p-mcp --setup-lumi --lumi-package <absolute MathDisplay.h5p path>; export never downloads it.' };
  }
}

export async function attachMathDependency(editor: Native, id: string, user: Native) {
  const saved = await editor.getContent(id, user);
  if (!containsLatex(saved.params.params)) return;
  const dependencies = saved.h5p.preloadedDependencies || [];
  if (!dependencies.some((d: Native) => d.machineName === MATH_LIBRARY.machineName)) {
    saved.h5p.preloadedDependencies = [...dependencies, MATH_LIBRARY];
    // Public storage API preserves the files already uploaded by Lumi.
    await editor.contentManager.createOrUpdateContent(saved.h5p, saved.params.params, user, id);
  }
}
