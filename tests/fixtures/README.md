# Pinned integration libraries

`libraries.zip` is a test-only snapshot of 24 H5P library directories used by the
integration tests, including their editor dependencies and original bundled
license notices. It is not included in the distributed package. `libraries.lock.json`
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
Its SHA-256 was checked by check_repository.py in the frozen Python baseline.
The retained Node/Bun probe generates a
0.2 second mono PCM WAV in its own temporary directory; no user media are used.

`tests/tooling/retirement-parity.mjs` verifies the library archive hash and unpacks
it into a unique temporary data directory. `tests/tooling/package-probe.ps1`
tests an installed Bun tarball with those libraries and an isolated package cache.
Package installation may require network access; content libraries come from the
pinned fixture, without H5P Hub requests or personal caches. CI runs on Windows,
Linux and macOS. Older Python fixture tooling remains in `python-final-f4`.
