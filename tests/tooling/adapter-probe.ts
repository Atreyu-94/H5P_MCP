import { firstLibrary } from './domain-probe.js';
export async function readLibrary(path: string): Promise<string | undefined> {
  const data: string = await Bun.file(path).text();
  return firstLibrary(data.split('\n'));
}
