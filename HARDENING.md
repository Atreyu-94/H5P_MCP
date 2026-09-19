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
| BATCH | 50 |
| SECONDS | 300 |

Media reads run sequentially and are bounded even if a file grows after stat.
ZIP prevalidation rejects duplicate names, unsafe paths and excess declared
sizes; JSON reads are bounded. Node input and Python output collection are
bounded. Process timeout and local interruption kill and reap the child.
Output is monitored in temporary files at 50 ms intervals; these are operational
budgets, not an OS memory/disk sandbox. MCP cancellation of a synchronous worker
is not guaranteed to terminate it immediately; its deadline still applies.

Optional `H5P_MCP_ASSET_ROOTS` is a JSON array of permitted absolute directories.
Roots and files are resolved before containment checks. Omit it to retain the
local MCP's existing absolute-path media workflow.

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
