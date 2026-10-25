# TECHNICAL — pathgate

Status: SCAFFOLD (not built). Date: 2026-10-12. Stack: Python 3.12 + `git` CLI (read-only plumbing); no paid deps; report-only.

## Architecture (C4-lite)

```
[git repo] → Ref enumerator (for-each-ref)
                    ↓
          Tree walker (ls-tree -r per ref; --history: rev-list --all + tree-OID dedup)
                    ↓
          Rule engine (reserved | illegal-char | trailing | length)
                    ↓
          Severity resolver (config: error | warn | info)
                    ↓
          Reporter: human | --json | --sarif
                    ↓
          Exit code (error findings → non-zero)
```

Single Python package `pathgate` (CLI). No services. No DB. **Report-only — never writes git objects or working tree.**

## Rules (v1)

| Rule id | Check | Default severity |
|---|---|---|
| `RESERVED_NAME` | basename (case-insensitive) in {CON, PRN, AUX, NUL, COM1–9, LPT1–9} (with/without extension) | error |
| `ILLEGAL_CHAR` | any of `: * ? " < > |` in path | error |
| `TRAILING_DOT_SPACE` | path ends with `.` or ` ` | error |
| `PATH_LENGTH` | path length > 260 | warn (config: error at >config) |

Defaults documented in docs/RULES.md; config overrides per-repo.

## Audit modes

- **All-refs-tips-first (v0.1 default):** `git for-each-ref --format='%(refname)'` → for each ref, `git ls-tree -r --name-only <ref>`; aggregate findings (dedup by path + rule).
- **History opt-in (`--history`):** `git rev-list --all` → for each commit, `git ls-tree -r --name-only <commit>` with **tree-OID dedup** (skip trees already seen) + progress bar. Perf budget [UNKNOWN] — Gate 0 spike measures on a real repo.

## Config

```yaml
# .pathgate.yaml
rules:
  RESERVED_NAME: error
  ILLEGAL_CHAR: error
  TRAILING_DOT_SPACE: error
  PATH_LENGTH: { severity: warn, max: 260 }
baseline: .pathgate-baseline     # optional: suppress known-existing
```

Baseline = JSON list of `{path, rule}`; new findings only reported.

## Interfaces

- CLI: `pathgate scan [--history] [--config c.yaml] [--json out.json] [--sarif out.sarif] [--baseline b.json]`; `pathgate rules list`; `pathgate doctor`.
- JSON schema: `{findings: [{path, rule, severity, refs: [...]}], summary: {errors, warnings, infos}}`.
- SARIF 2.1.0 output (GitHub code-scanning compatible).
- Exit codes: 0 ok / no error-severity; 1 error findings; 2 config error; 3 git error (not a repo); 4 environment (git missing).

## Data model

No persistence beyond report files + optional baseline JSON.

## Threat model (STRIDE-lite)

- **Read-only is the security model**: only `git` plumbing read commands (`for-each-ref`, `ls-tree`, `rev-list`, `cat-file` as needed); no `write-tree`, no `update-ref`, no working-tree writes. CI test asserts no git-mutating commands.
- Repo is untrusted input: huge trees, deep nesting, weird encodings → bounded memory (stream ls-tree output), clean errors.
- Path encodings: git stores paths as bytes; decode with surrogateescape; never crash on invalid UTF-8.
- Supply chain: stdlib-first; git CLI is system dependency (documented minimum version).

## Error model

Structured (rule-id style): `E_CONFIG`, `E_GIT`, `E_ENV`, `E_ENCODING`. Partial scan (one ref fails) = continue + warn, non-zero exit if any error-severity found.

## Performance budget

- All-refs-tips (100 refs, 10k files each): < 60s.
- History (10k commits): [UNKNOWN] — Gate 0 spike measures; target < 5 min with tree-OID dedup.
- Memory: stream, don't buffer all paths; bounded dedup set (hash of tree-OIDs).

## Testing strategy

- L0: ruff + mypy + pytest.
- L1: rule matchers (reserved, illegal char, trailing, length) — positive + negative.
- L2: fixture bare git repo with hostile paths across refs → correct findings; baseline suppresses known.
- L3: live audit of real repo on host (p2/p1 or clone) → SARIF valid.
- L4: fresh-clone README steps in CI.
- L5: empty repo, huge repo, non-git dir, invalid UTF-8 paths, non-ASCII.

## Packaging

PyPI `pathgate` (verify name free at G2). GitHub Action wrapper post-1.0.

## Repo layout (target)

```
pathgate/
  src/pathgate/{refs.py,rules.py,severity.py,report.py,cli.py}
  rules/v1.yaml
  fixtures/repos/ (bare git repos with hostile paths)
  tests/{unit,integration,security,adversarial}/
  docs/{PRODUCT,TECHNICAL,ROADMAP,EVIDENCE,RULES}.md
```
