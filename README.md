# pathgate

**Status: v0.1 built and verified (2026-10-25). Source published on GitHub; PyPI release remains owner-gated.**

Audit git refs and history for Windows-hostile paths — without checking out a single file.

Windows rejects certain path characters (`: * ? " < > |`), trailing dots/spaces, reserved names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`), and 260+ character paths (without long-path support enabled). Repos shared across Windows and Linux (open source, monorepos) often contain such paths; Windows clones fail or silently mangle them. `pathgate` reads git objects directly (`ls-tree`, `rev-list`) across **all refs** and optionally **full history** — no working tree, no checkout — and reports hostile paths with config-aware severity, JSON and SARIF output, and CI-friendly exit codes.

## Install

Requires Python 3.10+ and `git` on `PATH`. The only runtime dependency is PyYAML 6.0.2.

```bash
git clone https://github.com/maxico714/pathgate.git
cd pathgate
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\pip install .
```

Linux / macOS:

```bash
.venv/bin/pip install .
```

## Quickstart

Audit the current repository's ref tips:

```bash
pathgate scan
```

Audit another repository:

```bash
pathgate --repo ../some-repo scan
```

Real output from a fixture repository containing two hostile paths (timing varies):

```text
pathgate 1 refs, 3 paths, 111 ms
config: defaults

  [ERROR] RESERVED_NAME: CON
         refs: refs/heads/main
  [ERROR] ILLEGAL_CHAR: dir/file:bad.txt
         refs: refs/heads/main

Summary: 2 error(s), 0 warning(s), 0 info
```

Machine-readable output:

```bash
pathgate --repo ../some-repo scan --json report.json --sarif report.sarif
```

## Commands

| Command | What it does |
|---|---|
| `pathgate scan` | Audit every ref tip (default) |
| `pathgate scan --history` | Also walk history, deduplicated by tree OID (slower, opt-in) |
| `pathgate scan --dry-run` | List the active rules and severities without scanning |
| `pathgate scan --json FILE` | Write a JSON report |
| `pathgate scan --sarif FILE` | Write a SARIF 2.1.0 report |
| `pathgate rules list` | List rules with their effective severity |
| `pathgate doctor` | Check `git` availability and repository validity |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Scan completed; no `error`-severity findings (warnings and infos do not fail the run) |
| `1` | At least one `error`-severity finding |
| `2` | Usage or configuration error (argparse, invalid or unreadable config) |
| `3` | Target path is not a git repository |
| `4` | Scan incomplete: a ref/tree read or a report write failed |

## Rules

| Rule | Default | What it matches |
|---|---|---|
| `RESERVED_NAME` | error | Any path component (case-insensitive, extension stripped) is `CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9` |
| `ILLEGAL_CHAR` | error | Any Windows-illegal character (`:`, `*`, `?`, `"`, `<`, `>`, or the pipe) anywhere in the path |
| `TRAILING_DOT_SPACE` | error | Any path component ends with `.` or a space |
| `PATH_LENGTH` | warn | Path longer than `max` characters (default 260) |

## Configuration

`pathgate` reads `.pathgate.yaml` from the audited repository root, or the file given with `--config`. Unspecified rules keep their defaults.

```yaml
rules:
  RESERVED_NAME: error
  ILLEGAL_CHAR: error
  TRAILING_DOT_SPACE: error
  PATH_LENGTH:
    severity: warn
    max: 260
baseline: .pathgate-baseline.json
```

Set a rule to `error`, `warn` or `info` (case-insensitive). `PATH_LENGTH` accepts either a bare severity (`PATH_LENGTH: info`) or a mapping with `severity` and `max` as above. Invalid severities, a non-mapping `rules` value, unreadable YAML, and a `max` that is not a positive integer stop the run with exit code 2 and an explanatory message.

## Baseline

Suppress findings that already exist in a repository so CI only fails on new ones. Pass `--baseline FILE` or set `baseline:` in the config (resolved relative to the audited repository).

```json
[
  {"path": "docs/CON", "rule": "RESERVED_NAME"},
  {"path": "legacy/a:b.txt", "rule": "ILLEGAL_CHAR"}
]
```

The file can be either a plain array as shown above or a previous `pathgate scan --json` report (its `findings` array is used). An unreadable baseline prints a warning and is ignored; the scan still runs.

## Report-only guarantee

`pathgate` never rewrites history, never checks out files and never modifies the audited repository. It only reads git objects and writes the report files you explicitly request with `--json` / `--sarif`. Renaming or history rewriting is out of scope and would be a separate, human-gated tool.

## Verification (2026-10-25, Windows 11, Python 3.12.10; QA re-run 2026-10-28)

| Check | Result |
|---|---|
| Test suite | `pytest -q` → **60 passed** on Python 3.12.10 and 3.14.5 |
| Lint / format | `ruff check src tests` and `ruff format --check src tests` clean |
| Types | `mypy src` → no issues (strict) |
| Mutation checks | Disabling reserved-name matching failed 2 tests; limiting the rule to the last path component failed 1 test; restored and re-ran green |
| Packaging | Wheel `pathgate-0.1.0-py3-none-any.whl` (15,655 bytes, SHA-256 `82d07b9525a613f0132ba75a8b35f9cc24880726f76218d289afcad748b274c2`) and sdist built; `twine check` passed for both |
| Clean install | Fresh venv + wheel install; `--history` scan of a fixture found a reserved directory (`CON/readme.txt`) and a trailing-dot directory (`dir./file.txt`), wrote JSON and SARIF 2.1.0 |
| SARIF | Valid against the SARIF 2.1.0 JSON schema; levels use `error`/`warning`/`note`; artifact URIs are percent-encoded; no placeholder URIs |
| Non-UTF-8 paths | Surrogateescaped git paths render in human/JSON output; SARIF percent-encodes the raw bytes without crashing |
| Failure paths | Failed ref/tree reads and unwritable reports exit 4; invalid config exits 2; a repo whose refs fail is never reported as clean |
| Secrets | `detect-secrets` on all tracked files → 0 findings (full git history not separately scanned) |
| PyPI name | `pypi.org/pypi/pathgate/json` returned 404 on 2026-10-25 (no project registered at check time; re-check before publishing) |
| Read-only | Fixture HEAD unchanged after the scan |

Not yet verified: behavior on Python 3.10/3.11 (not installed locally), the CI workflow (added but never executed — there is no remote), performance of `--history` on very large repositories, and a scan of a large real-world repository.

## Limitations and non-goals

- **Report-only.** No rewriting, renaming or removal of paths.
- **History mode is opt-in and experimental.** It walks unique trees per commit through separate `git` calls; wall time on repositories with tens of thousands of commits is unmeasured.
- **Path length is a character count.** Windows measures paths differently once long-path support and extended prefixes are involved; `max` is configurable for this reason.
- **Windows-specific target.** The rules encode Windows restrictions; they are not a general-purpose path linter.
- Non-UTF-8 paths are decoded with `surrogateescape` and are not expected to crash the scanner.

## Documents

- [docs/PRODUCT.md](docs/PRODUCT.md) — problem, personas, MoSCoW, success criteria
- [docs/TECHNICAL.md](docs/TECHNICAL.md) — audit engine, severity model, interfaces
- [docs/ROADMAP.md](docs/ROADMAP.md) — v0.1 → v1.0
- [docs/EVIDENCE.md](docs/EVIDENCE.md) — verified evidence and binding conditions
- [BUILD_CHECKLIST.md](BUILD_CHECKLIST.md) — ordered build and verification steps

## License

MIT.
