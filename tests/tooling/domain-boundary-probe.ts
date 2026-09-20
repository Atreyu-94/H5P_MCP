// This must stay an error: domain code has no runtime-specific globals.
// @ts-expect-error Bun is intentionally absent from the domain type environment.
export type ForbiddenRuntime = typeof Bun;
