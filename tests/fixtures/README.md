# Pinned integration libraries

`libraries.zip` is a test-only snapshot of 23 H5P library directories used by the
integration tests, including their editor dependencies and original bundled
license notices. It is not included in the Python wheel. `libraries.lock.json`
records its SHA-256, patch versions, and library metadata. A missing metadata
license is not a declaration that the files have no license; consult their
bundled notices. These are third-party assets, not Apache-licensed project code.

Source: the explicitly installed H5P Hub libraries used for the Core 1.28 tests;
MathDisplay 1.0.50 came from
https://h5p.org/sites/default/files/h5p-math-display-1-0-50.h5p.
Snapshot created 2026-09-19. Review library changes and regenerate the checksum
deliberately; tests must not update this fixture from the Hub automatically.

Integration tests unpack it into a unique temporary data directory by default.
Set `H5P_MCP_ISOLATED_TESTS=0` only for an explicit developer-cache run.
The pinned Lumi runtime is installed there with `npm ci --ignore-scripts`.
This requires npm network access on first installation, but no H5P Hub request
and no personal library cache. CI uses this mode on Windows and Linux.
