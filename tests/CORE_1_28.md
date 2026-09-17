# Core 1.28 verification

Verified on Windows, 2026-09-17, with Node 26.7 and Chrome headless.
Backend: Lumi commit `efcfeebc6d7ae349f4fb708e2f44284151f77558`.
Browser Core assets: official `h5p/h5p-php-library` commit
`2aeb0b83fa603e331381b3a6b8bf42c3773ba140` (the revision used by Lumi).

- `python -m pytest -q`: 63 passed. Includes all four activity types, real
  import into empty storage, Core 1.28 acceptance / 1.29 rejection, missing
  libraries, invalid JSON roots and protection against overwriting exports.
- Built the wheel and sdist with `uv build`. The wheel contains the compiled
  npm archive, server source, license, lockfile and provenance manifest.
- Three stdio MCP tests passed using the wheel via isolated `uvx`.
- A fresh wheel setup installed the backend using a local QuestionSet package
  containing all four libraries, without relying on the development cache.
- `lumi_browser_smoke.cjs` loaded seven sample packages in Chrome, covering
  MCQ, TrueFalse, Blanks and QuestionSet. It checked resource requests, uncaught
  exceptions, visible content, answer controls and numeric scores. All passed.

Re-run the Python tests after `uv run h5p-mcp --setup-lumi`. To test a wheel:

```powershell
uv build
$env:H5P_MCP_TEST_COMMAND = '["uvx", "--isolated", "--from", "<absolute wheel path>", "h5p-mcp"]'
uv run pytest -q tests/test_mcp_stdio.py tests/test_skills_stdio.py
```

For browser smoke tests, generate samples into a new export directory and pass
four absolute paths to the script: installed npm runtime, upstream checkout
with `@playwright/test` installed, extracted official Core directory, and sample
package directory. The script starts an ephemeral localhost server and closes
Chrome and the server on completion. It stubs learner-state endpoints; it is
not a persistence or gradebook test.

```powershell
node tests/lumi_browser_smoke.cjs <runtime> <upstream> <core> <packages>
```

Not verified: Moodle import/grade transfer, Lumi Desktop, accessibility,
multimedia activities, other operating systems or the minimum Node 22.12
runtime. Browser interaction is a smoke check, not an exhaustive assessment
of all answer combinations or QuestionSet completion.

The interim upstream build can be rebuilt using PowerShell 7:
`./h5p_mcp/lumi/build-upstream.ps1`. This downloads the pinned source into a
fresh temporary directory and installs its upstream lockfile without lifecycle
scripts. After rebuilding, update the local npm lockfile with
`npm install --ignore-scripts --no-audit --no-fund ./lumieducation-h5p-server-10.0.4-h5pmcp.efcfeebc.tgz`
from `h5p_mcp/lumi`. The script updates the archive checksum in provenance;
do not relabel a different upstream revision as this build.
