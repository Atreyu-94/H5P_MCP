# H5P MCP Quiz Generator (Python)

Generate **valid H5P quiz packages (`.h5p`)** from **pure Python** via an **MCP server** (FastMCP). Designed to be used by **Claude Desktop**, **Cursor**, or any MCP-compatible agent—**no frontend** required.

This project outputs real H5P package structure:

- `h5p.json`
- `content/content.json`

It **does not bundle H5P libraries** (that’s normal for content exports). Your target platform (Moodle, Lumi, etc.) must have these content types installed:

- `H5P.MultiChoice`
- `H5P.TrueFalse`
- `H5P.Blanks`
- `H5P.QuestionSet`

## Project structure

```
h5p_mcp/
├── server.py
├── requirements.txt
├── README.md
├── templates/
│   ├── mcq/
│   ├── truefalse/
│   └── blanks/
├── generators/
│   ├── mcq_generator.py
│   ├── truefalse_generator.py
│   └── blanks_generator.py
├── exporters/
│   └── h5p_exporter.py
├── validators/
│   └── quiz_validator.py
├── utils/
│   ├── zip_utils.py
│   └── file_utils.py
├── models/
│   └── quiz_models.py
└── exports/
```

## Setup

### Requirements
- [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Python **3.12+**; uv can download the interpreter selected by `.python-version`.

### Development from a checkout

Run from the repository root:

```powershell
uv sync --locked
uv run --locked pytest
uv run --locked h5p-mcp
```

`pyproject.toml` declares the package and dependencies. Commit `uv.lock` to keep
development and CI environments reproducible. Upgrade dependencies deliberately
with `uv lock --upgrade`, then rerun the tests. The supported dependency ranges
start at the versions used in the migration audit.

The server uses MCP stdio. `uv run --locked python -m h5p_mcp.server` remains
available. A pip compatibility installation is `python -m pip install .` from
the root (or `python -m pip install -r h5p_mcp/requirements.txt`); pip does not use
`uv.lock`.

### Run the installed tool with uvx

From a checkout, build and test the distributable wheel:

```powershell
uv build
uvx --from ./dist/h5p_mcp-0.1.0-py3-none-any.whl h5p-mcp --help
```

Once this migration has been committed and pushed, clients can install directly
from GitHub without a checkout. Replace `COMMIT` with the full commit SHA that
contains the packaging changes:

```powershell
uvx --from "git+https://github.com/Atreyu-94/H5P_MCP.git@COMMIT" h5p-mcp
```

There is no PyPI publication in this migration. `uvx h5p-mcp` is not an
installation instruction for this fork. uvx resolves the package's dependencies
independently of the checkout's `uv.lock`; pinning a Git commit fixes the source,
but does not freeze every transitive dependency. Use the locked checkout when
exact dependency reproduction is required.

### Export location

Set `H5P_MCP_EXPORT_DIR` to an absolute, writable directory for generated activities.
If omitted, files go to `exports/` in the server's working directory. Earlier
versions wrote inside `h5p_mcp/exports`; installed tools now keep user files out
of their installation and uv cache. Existing activities are not moved.

### Connect an MCP client

For development, use an absolute checkout path (replace the example paths):

```json
{
  "mcpServers": {
    "H5P_MCP": {
      "command": "uv",
      "args": ["run", "--directory", "D:/path/H5P_MCP", "--locked", "--no-dev", "h5p-mcp"],
      "env": {"H5P_MCP_EXPORT_DIR": "D:/path/activities"}
    }
  }
}
```

For an installed release, replace `command` with `uvx` and `args` with
`["--from", "git+https://github.com/Atreyu-94/H5P_MCP.git@COMMIT", "h5p-mcp"]`.
Keep the explicit export directory. Use the full executable path if the desktop
client cannot find uv on its PATH. The same stdio command works in clients such
as Claude Desktop and Cursor; adapt the enclosing configuration to the client.

### Verify the wheel through MCP

After `uv build`, run the same stdio test against the isolated wheel installation:

```powershell
$env:H5P_MCP_TEST_COMMAND = ConvertTo-Json -Compress -InputObject @("uvx", "--from", (Resolve-Path ./dist/h5p_mcp-0.1.0-py3-none-any.whl).Path, "h5p-mcp")
uv run --locked pytest tests/test_mcp_stdio.py -q
Remove-Item Env:H5P_MCP_TEST_COMMAND
```

The test launches the server outside the checkout and exports all four activity
types, checking that the packaged JSON templates are available. This is a
packaging/protocol test, not a Moodle import or grading test.

## MCP tools provided

- `create_mcq_quiz(title, question, choices, correct_answer, explanation)`
- `create_true_false_quiz(title, question, correct_answer, explanation)`
- `create_fill_blanks_quiz(title, text, answers)`
- `create_questionset_quiz(title, intro, questions, pass_percentage)`
- `export_h5p(quiz_data, output_name)`
- `validate_h5p(path)`
- Bonus:
  - `export_h5p_batch(quizzes, name_prefix)`
  - `markdown_to_quizzes(markdown)`
  - `h5p_prompt_helpers()`

## Example prompts for an AI agent

### Create and export an MCQ

Ask your agent to:

- Call `create_mcq_quiz` with:
  - title: “Basic Math”
  - question: “What is 2 + 2?”
  - choices: ["3","4","5"]
  - correct_answer: "4"
  - explanation: "2 + 2 equals 4."
- Then call `export_h5p` with:
  - quiz_data: (result from create tool)
  - output_name: "basic_math_mcq"

### Create and export a Fill in the Blanks

Use blanks text with **asterisk-wrapped answers** (H5P.Blanks convention):

- text: `"The capital of France is *Paris*."`

And provide answers list to validate:
- answers: ["Paris"]

## Generate sample `.h5p` files

Run:

```bash
uv run --locked h5p-mcp --generate-samples
```

This writes a **set of sample `.h5p` files** (including a mixed-type `QuestionSet`) into `exports/`.

## Markdown-to-quiz format (bonus)

```text
### MCQ: Basic Math
Q: What is 2 + 2?
- [ ] 3
- [x] 4
- [ ] 5
Explanation: 2 + 2 equals 4.

### TF: Astronomy
Q: The Earth orbits the Sun.
A: true
Explanation: It takes about one year.

### Blanks: Capitals
Text: The capital of France is *Paris*.
Answers: Paris
```

Then:
- Call `markdown_to_quizzes(markdown)` to get canonical quiz objects
- Call `export_h5p_batch(quizzes, name_prefix)` to export them

## Notes on Moodle / Lumi compatibility

- The produced `.h5p` contains content JSON compatible with the declared library.
- Moodle/Lumi must already include the relevant H5P libraries (content types).
- Validation in this repo checks package shape + JSON sanity and detects obvious issues early.

## License

Apache 2.

