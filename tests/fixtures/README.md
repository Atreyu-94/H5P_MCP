# Pinned integration libraries

`libraries.zip` is a test-only snapshot of 24 H5P library directories used by the
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

Audio 1.5.29 was added through the explicit isolated Hub probe on 2026-09-19.
Both Node and Bun installed that version; its original notices are preserved.

`video.webm` is project-generated test data: 0.2 seconds of 32x32 blue VP9 video,
created with FFmpeg 9.0.1 (`-f lavfi -i color=c=blue:s=32x32:d=0.2 -an -c:v libvpx-vp9`).
Its SHA-256 is enforced by check_repository.py. The runtime probe generates a
0.2 second mono PCM WAV in its own temporary directory; no user media are used.

Integration tests unpack it into a unique temporary data directory by default.
Set `H5P_MCP_ISOLATED_TESTS=0` only for an explicit developer-cache run.
The pinned Lumi runtime is installed there with `npm ci --ignore-scripts`.
This requires npm network access on first installation, but no H5P Hub request
and no personal library cache. CI uses this mode on Windows and Linux.
