# H5P MCP authoring

Create H5P activities through FastMCP and Lumi, using each installed content
type's native schema instead of four fixed quiz templates.

## Workflow

1. `search_h5p_types(query, installed_only, offset, limit)` discovers
   cached Hub entries and installed runnable libraries. Default page size 20,
   maximum 100. `refresh_h5p_catalog` explicitly contacts the Hub; a fresh cache may be
   empty. `last_updated` is Unix time in milliseconds, or null.
2. `get_h5p_type_contract(machine_name, major_version, minor_version)` returns
   compact native fields, constraints, sublibraries and a raw-schema resource. Supply both
   version numbers for an exact version, or neither for newest installed.
   `install_h5p_library` downloads the current Hub version and dependencies if
   absent and administration is enabled. Historical versions are not substituted.
3. `prepare_h5p_activity(title, library, params, language="en", license="U",
   assets={})` returns a versioned report with diagnostics and `activity`. It checks exact-version
   native fields and fills declared defaults and nested subcontent IDs.
4. If `ok=true`, pass the normalized `activity` to
   `export_h5p_activity(activity, output_name)`. It rechecks and packages content,
   assets and libraries, returning a resource link, SHA-256, size and manifest.
   Existing files are never overwritten; downloads are never implicit.
5. Read the artifact resource to retrieve the package. Use `validate_h5p_package(path)`
   for an authorized local package. Legacy `export_h5p` still returns a local path.

`export_h5p_batch(activities, name_prefix="activity")` returns per-item results,
`count` and `succeeded`. Successful files remain when another item fails.

`authoring_supported` is generic authoring eligibility, not playback verification.
Hub Core compatibility describes the Hub version; authoring checks the exact
installed version. Supporting libraries may expose schemas without being runnable
main activities. Read nested library schemas separately at their exact versions.

### Example: Accordion

First read schemas for `H5P.Accordion 1.0` and `H5P.AdvancedText 1.1`, installing
explicitly if needed. Then call `create_h5p_activity`:

```json
{
  "title": "Cambios de estado",
  "library": "H5P.Accordion 1.0",
  "language": "es",
  "params": {
    "panels": [{
      "title": "Evaporación",
      "content": {
        "library": "H5P.AdvancedText 1.1",
        "params": {"text": "<p>El agua pasa de líquido a gas.</p>"}
      }
    }]
  }
}
```

Inspect the report, export its `activity`, then validate the returned file.
These versions are examples, not latest-version claims. Native H5P semantics are
not JSON Schema. One-field groups use the child value directly, for example
`overallFeedback` is a list rather than an object wrapping a list.

### Media

Use `{"path":"asset:diagram","mime":"image/png"}` in a native image/file field
and `assets={"diagram":"C:/absolute/diagram.png"}` at activity level. Audio/video
fields contain lists of media objects. Lumi checks formats, determines image
dimensions and embeds files, preserving source files. Missing and unreferenced
asset mappings are rejected. Remote HTTP(S) media remain URLs and need network
access during playback. Core 1.28 may reject SVG/office attachments by default.

## Mathematical notation

Write LaTeX explicitly as `\( ... \)` (inline), `\[ ... \]` or `$$ ... $$`
(display). JSON requires doubled backslashes. The MCP scans nested content and
feedback for delimiters and returns a `mathematics` report during creation.
Unicode text such as `kg/m³` is not automatically converted to LaTeX.

Install the official [MathDisplay addon](https://h5p.org/mathematical-expressions)
explicitly with `h5p-mcp --setup-lumi --lumi-package <absolute path>`.
It is an addon, not a runnable Hub activity. Missing MathDisplay blocks LaTeX
authoring/export with setup instructions; export never downloads it. When math
is detected, exports include `H5P.MathDisplay 1.0` as an explicit preloaded
dependency and package its installed files through Lumi. Content without LaTeX
does not gain that dependency.

Keep mathematical answer tokens in Blanks, DragText and MarkTheWords plain when
their parsers require it; render formulas in rich-text prompts and feedback.
MathDisplay renders notation; it does not grade symbolic equivalence, validate
TeX syntax or automatically translate plain formulas. Test dynamic feedback and
each chosen content type in the destination. Moodle must permit installation of
the bundled library in the H5P integration used by the activity. Updating Core
alone does not enable math rendering.

## Breaking migration

Removed: `create_mcq_quiz`, `create_true_false_quiz`, `create_fill_blanks_quiz`,
`create_questionset_quiz`, their models/generators/templates,
`markdown_to_quizzes`, `h5p_prompt_helpers` and `--generate-samples`.
Existing `.h5p` files are unaffected. The original four types remain usable
through generic authoring.

Replace export argument `quiz_data` with `activity`, and batch `quizzes` with
`activities`. Convert source data to native params after reading schemas:
TrueFalse uses `params.correct="true"`, not `correct_answer=true`. Clients must
refresh tool discovery after restarting.

## Installation

Requires uv, Python 3.12+, Node.js 22.12+ and npm. From the repository:

```powershell
uv sync --locked
uv run --locked h5p-mcp --setup-lumi
uv run --locked h5p-mcp
```

Setup installs pinned Node dependencies. Choose libraries through explicit schema
downloads, or install libraries from trusted local packages:

```powershell
uv run --locked h5p-mcp --setup-lumi --lumi-package C:/absolute/example.h5p
```

`--lumi-package` is repeatable and installs libraries, not authored content.
`H5P_MCP_DATA_DIR` overrides the shared runtime/library cache.
`H5P_MCP_EXPORT_DIR` selects an absolute writable export directory; otherwise
files go to `exports/` in the server's working directory.

For uvx, use the same source for setup and server startup:

```powershell
uvx --from "git+https://github.com/Atreyu-94/H5P_MCP.git@COMMIT" h5p-mcp --setup-lumi
uvx --from "git+https://github.com/Atreyu-94/H5P_MCP.git@COMMIT" h5p-mcp
```

Replace COMMIT with a full commit SHA. This fork is not published on PyPI. uvx
resolves dependencies independently of uv.lock; use a locked checkout for exact
reproduction. MCP uses stdio. For local development, client command `uv` can use
arguments `run --directory C:/absolute/H5P_MCP --locked h5p-mcp`. Allow 300 seconds
for explicit library downloads.

## Educational skill

The packaged [h5p-authoring skill](h5p_mcp/skills/h5p-authoring/SKILL.md) guides
activity selection, schemas, feedback, assets, export and Moodle handoff.
The server exposes `io.modelcontextprotocol/skills` through FastMCP's public API.
`skills/list` and `skills/get` are tested on protocol `2026-07-28`. Read
`skill://h5p-authoring/SKILL.md` using `resources/read`. Entries carry frontmatter,
raw-byte SHA-256 and size; no directory-reading extension is advertised.
Ordinary clients can read the resource; native skill activation depends on client
support. Restart after changing the skill's startup snapshot.

## Validation limits and Core

Checks cover required fields, primitive types, select choices, list/number bounds,
exact nested libraries and asset references. Unknown fields/types fail explicitly.
Defaults come from installed semantics; language metadata does not translate UI
labels. Widget rules, conditional UI behavior, HTML sanitization and pedagogical
correctness are not fully validated. Generic authoring does not guarantee every
Hub activity works without additional editor logic or external services.

Import validation is not playback, accessibility or grade-transfer testing.
Check those in the target Moodle, whose Core and permissions must accommodate the
packaged libraries.

Lumi is pinned to upstream commit `efcfeebc6d7ae349f4fb708e2f44284151f77558`,
supporting Core 1.28.0. This is an interim development build, not an official stable
release. `h5p_mcp/lumi/provenance.json` records source and checksum;
`build-upstream.ps1` rebuilds the bundled archive. This does not upgrade Lumi
Desktop or Moodle Core.

## Development checks

Integration tests require installed TrueFalse 1.8, MultiChoice 1.16, Blanks 1.14,
QuestionSet 1.21, Accordion 1.0 and dependencies including AdvancedText 1.1 and
Image 1.1. Install explicitly through administrative tools or trusted packages. Tests
never silently fetch missing activity libraries.

```powershell
uv run --locked pytest
uv build
$wheel = (Resolve-Path ./dist/h5p_mcp-0.1.0-py3-none-any.whl).Path
$env:H5P_MCP_TEST_COMMAND = ConvertTo-Json -Compress -InputObject @('uvx', '--from', $wheel, 'h5p-mcp')
try {
    uv run --locked pytest tests/test_skills_stdio.py tests/test_mcp_stdio.py
} finally {
    Remove-Item Env:H5P_MCP_TEST_COMMAND
}
```

Stdio tests use reference clients and fixed fixtures, not autonomous LLM
selection. Browser/Core evidence is in [tests/CORE_1_28.md](tests/CORE_1_28.md).

## License

Python project: Apache 2.0. Bundled Lumi server and corresponding source:
GPL-3.0-or-later, with LICENSE included in the npm archive. Other dependencies
retain their authors' licenses.

## Authoring guarantees and reproducible tests

See [HARDENING.md](HARDENING.md) for preparation manifests, stable diagnostics,
resource limits, verification stages and isolated integration tests.

## Versioned preparation contract (F2/C10)

`prepare_h5p_activity` is the new local preparation interface. It accepts the
same title, exact library, native params, language, license and local assets as
`create_h5p_activity`. On success, pass its `activity` object to `export_h5p`.
The existing tools remain available during migration.

Reports use `contract_version: "1"`. Invalid input returns `ok: false` with
`kind: "validation"`; backend failures return `kind: "operational_error"` and
MCP `isError: true`. Diagnostics include an escaped JSON Pointer, stable code,
retryability and a suggested correction. At most 100 diagnostics are returned,
with `diagnostics_truncated` indicating omitted entries. Failed preparations
do not return the activity or raw backend messages. Unexecuted verification
stages remain `not_run`; preparation does not certify Moodle playback/grading.

Read `h5p-contract://v1/schema` and `h5p-contract://v1/codes` through MCP resources
for the packaged JSON authority. This increment has no persistent preparation
IDs or remote profile; those require the later storage phase. See
[F2 implementation status](docs/architecture/005-f2-contracts.md) for the scope
and remaining increments.

## Local library administration (F2/C11)

Administration is disabled by default. To enable selected administrative tools
for a local stdio process, set host environment variables before starting it:

```powershell
$env:H5P_MCP_ADMIN_SCOPES = 'catalog:refresh libraries:install'
h5p-mcp
```

`catalog:refresh` exposes `refresh_h5p_catalog`. `libraries:install` exposes
`install_h5p_library` and `install_h5p_library_package(path)`. Local package
installation enforces ZIP checks and `H5P_MCP_PACKAGE_ROOTS`, may update existing
libraries, and never initializes npm or downloads Hub content implicitly.
Grant either scope independently; unknown scope names fail startup.

`H5P_MCP_IMMUTABLE=1` hides and rejects every administrative tool regardless of
scopes, and disables `--setup-lumi`. Configuration is frozen at process startup.
Tool annotations do not grant permissions. Calling a hidden tool directly is
also rejected, including through stdio. These are local host permissions, not
OAuth or a remote multi-tenant security boundary.

Legacy `list_h5p_activities(refresh=true)` and
`get_h5p_activity_schema(install_if_missing=true)` require the corresponding
scope. Their default read operations remain compatible. Ordinary catalog/schema
queries preserve library/cache/configuration contents and use cleaned temporary
storage. The existing backend coordination lock is still used to serialize reads
against installations. CLI setup remains an explicit operator action in mutable
mode and does not require MCP tool scopes.

## Compact native contracts (F2.6)

`get_h5p_type_contract` describes installed semantics without installation or
network access. Its `fields` retain order, names, types, native required flags,
defaults and constraints. `x-h5p` retains widget/extension metadata and explains
limits. Groups with `value_shape: "single_field"` use the child's value directly.
This format is not JSON Schema and does not certify editor business logic.
Labels, descriptions and UI grouping flags are available in the raw resource.

`raw_schema` returns a URI, SHA-256, MIME and byte length of a canonical UTF-8
JSON snapshot containing complete native semantics and library metadata. The
digest refers to those exact resource bytes, not the original file formatting.
Resources are bounded process-local snapshots: defaults are 2 MiB per resource,
16 snapshots and 16 MiB total. Configure `H5P_MCP_MAX_SCHEMA_BYTES`,
`H5P_MCP_MAX_SCHEMA_SNAPSHOTS` and `H5P_MCP_MAX_SCHEMA_CACHE_BYTES` if needed.
After eviction or restart, call the tool again; resource reads never resolve
user-supplied filesystem paths or download anything.

Examples are currently included for TrueFalse 1.8 patch 21 only when its native
semantics SHA-256 matches the tested fixture. Other contracts return an empty
examples array. Tests exercise both published examples through real preparation;
they do not claim playback or grading evidence in Moodle.

## F2 operation contracts and evidence

`h5p-contract://v1/profiles` publishes resolved input/output schemas for the
local operations and separate ID-only remote input schemas. Remote execution is
disabled: durable preparation IDs/ownership require F5, and HTTP/auth requires F6.
Local export accepts the prepared activity object and its dependency manifest.
Native `params` remain dynamic; remote assets bind opaque IDs, never host paths.

The catalog now reports `structurally_authorable` and per-installed-version
evidence: library/patch, timestamp, schema digest, runnable/core/type checks and
unexecuted preparation/import/playback/grading checks. `authoring_supported` is a
compatibility alias. Hub presence alone is not authorability or test evidence.

New operations validate closed input envelopes and return bounded diagnostics.
Invalid content has `ok=false` without MCP `isError`; operational failures set
`isError=true`. Batch retains per-item results and marks operational failures;
successful files remain. Legacy tool names and synchronous APIs stay available.

Export tools return a `resource_link`, never package base64. Binary resource reads
use the MCP protocol encoding, verify size/digest and default to 16 MiB maximum
(`H5P_MCP_MAX_RESOURCE_BYTES`). The process keeps at most 128 registered artifacts
(`H5P_MCP_MAX_ARTIFACTS`); eviction/restart invalidates their IDs without deleting
exported files. The manifest includes the exact preparation dependency snapshot.
Oversized resources require a higher local read limit or a smaller package.
