# Authoring guarantees and operational limits

Preparation checks native field types, required fields/defaults, list bounds,
select options, numeric bounds and decimal precision, explicit text regexps,
and explicit plain-text length limits. HTML widgets ignore `maxLength` as H5P
specifies. Values affecting answers are rejected rather than rounded. Widget
business rules, HTML sanitization, accessibility and symbolic equivalence are
not covered by these checks.

Missing nested `subContentId` values receive UUIDs. Supplied UUIDs must be valid
and unique within the activity; valid identities survive repeated preparation.
To intentionally duplicate a subtree, remove its IDs before preparing the new
composition. Export never silently repairs duplicate identities.

Prepared activities carry an opaque `preparation` manifest: SHA-256 hashes of
library files, patch versions, local assets and backend source identity. Preserve
this field when exporting. Changes produce `STALE_PREPARATION`; prepare again
and review the new result. Raw activities remain accepted for compatibility and
are checked at export, but have no earlier preparation to compare against.
This detects drift; it does not archive historical libraries, freeze remote media,
or promise byte-identical ZIPs. Local files are checked again after export, before
exclusive publication. Concurrent hostile filesystem modification is outside
this local author's trust model; hashes are not filesystem isolation.

Reports expose `verification`: structure, semantics, importation, playback and
grading each use `passed`, `failed` or `not_run`. Export does not itself run an
import, browser or Moodle grading test. FastMCP clients may deserialize typed
reports as objects; use `structured_content` for the JSON dictionary contract.

## Budgets

Positive integer environment variables configure these defaults:

| Variable suffix after `H5P_MCP_MAX_` | Default |
|---|---:|
| JSON_BYTES | 16777216 |
| OUTPUT_BYTES | 33554432 |
| DEPTH | 64 |
| NODES | 100000 |
| ASSET_BYTES | 67108864 |
| MEDIA_BYTES | 268435456 |
| ZIP_MEMBERS | 20000 |
| ZIP_MEMBER_BYTES | 134217728 |
| ZIP_BYTES | 536870912 |
| ZIP_ARCHIVE_BYTES | 134217728 |
| ZIP_RATIO | 1000 |
| ZIP_PATH_DEPTH | 32 |
| LIBRARIES | 1000 |
| DEPENDENCY_EDGES | 5000 |
| DEPENDENCY_DEPTH | 32 |
| BATCH | 50 |
| SECONDS | 300 |

Media reads run sequentially and are bounded even if a file grows after stat.
ZIP validation checks compressed size before opening, bounds expansion ratio,
and drains members in 64 KiB chunks to check readable byte counts and CRC before
Lumi import. It rejects symlinks/special entries, ambiguous separators, Windows
reserved names/ADS, Unicode NFC/case-fold collisions and file/directory conflicts.
Explicit directory entries remain allowed. Package validation and administrative
installation share this preflight. A version-specific adapter bounds Lumi's ZIP
extraction in the isolated worker, including streamed bytes and exclusive files.
The worker also rejects portable path collisions (NFC/lowercase); Python preflight
additionally applies full Unicode case folding. The preflight and later import are not an immutable
file snapshot. JSON reads are bounded. Node input and Python output collection are
bounded. Process timeout and local interruption kill and reap the child.
Output is monitored in temporary files at 50 ms intervals; these are operational
budgets, not an OS memory/disk sandbox. MCP cancellation of a synchronous worker
is not guaranteed to terminate it immediately; its deadline still applies.

Optional `H5P_MCP_ASSET_ROOTS`, `H5P_MCP_PACKAGE_ROOTS`, and
`H5P_MCP_EXPORT_ROOTS` are JSON arrays of permitted absolute directories.
Roots and paths are resolved before containment checks; an empty array denies
all access of that kind. Omit a variable to retain the existing local absolute-path
workflow. These controls do not prevent a hostile local process replacing a path
between resolution and opening; stronger snapshots/isolation belong to the remote
storage phase. Internal disposable import/export paths are not user-selected roots.

Local media must match detected magic bytes and the declared MIME allowlist:
raster images, supported audio/video containers, PDF and WebVTT. SVG and HTML are
rejected. Magic bytes do not establish codec validity or browser playback. The same
bounded bytes inspected for MIME are sent to Lumi; remote playback URLs are not
downloaded. Dependency manifests bound nodes, edges and depth and reject cycles.

The backend deadline includes lock contention. Publication uses an exclusive hardlink
or a platform no-replace rename; it never copies to a visible final filename.
Unsupported atomic primitives fail explicitly. Linux/macOS fallback implementation
is covered by portable tests but requires execution on those platforms.

MathDisplay remains the only explicitly resolved addon. Other installed addons
are not exported indiscriminately. Add new adapters only with a real content
type and regression evidence.

## Repeating verification

Run `python -m pytest tests/test_hardening.py` for offline boundary regressions.
Integration tests use isolated libraries by default (`H5P_MCP_ISOLATED_TESTS=1`);
set it to `0` only to explicitly reuse a developer cache. The
fixture lock is checked before use. CI builds a wheel, installs it, copies tests
outside the checkout and runs with isolated libraries on Python 3.12/3.13 and
Windows/Linux using Node 22.12.

The browser smoke supports `H5P_MCP_GRADING_SMOKE=1` for a True/False fixture
whose correct answer is True, with retry enabled and LaTeX in both feedback
branches. This exercises exact wrong/correct scores and retry, not a Moodle
gradebook or all activity types. Browser prerequisites remain explicit in the
smoke script; browser tests are not part of the Python CI matrix.
