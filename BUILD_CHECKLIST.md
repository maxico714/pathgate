# BUILD CHECKLIST — pathgate

Status: v0.1 locally verified 2026-10-25 (59 tests, ruff/mypy clean, wheel installs in a fresh venv). Gates 1–3, 6.1–6.3, 7.1 and 8.1 are done; remaining boxes are open. G2 (public push) and G3 (publish) were not executed. Work top-to-bottom; each gate shows REAL command output. Circuit breaker: 3 failures per gate → stop, re-research, log in STATE.md.

## Gate 0 — Perf spike (riskiest assumption FIRST) — **PARTIALLY DONE 2026-10-12**

Spike results (synthetic repo: 200 files, 10 commits, PowerShell subprocess per git call):
- `for-each-ref`: 75 ms (1 ref)
- `rev-list --all`: 79 ms (10 commits)
- `all-refs-tips ls-tree`: **80 ms** (200 paths at tips) — well within 60s budget ✓
- `history ls-tree + tree-OID dedup`: **1579 ms** (10 unique trees, 1100 paths) — ~160ms/commit subprocess overhead in PowerShell

**Verdict:** all-refs-tips mode confirmed fast. History mode: PowerShell per-commit subprocess is too slow for 10k+ commits (~27min extrapolated); **Python implementation must use single-subprocess `git log --all --name-only --pretty=format:`** (not per-commit ls-tree) — likely 10-50x faster. [UNKNOWN] remains for huge repos (100k+ commits) — re-measure with Python batched approach at build time.

- [ ] Re-run spike with Python single-subprocess batched git-log approach; log wall time + findings in DECISIONS.md. If still > 5 min on a real mid-size repo → history stays experimental / opt-in only.

## Gate 1 — L0 static (every commit)

- [x] `ruff check .` + `ruff format --check .` clean.
- [x] `mypy src/` clean.
- [x] `pytest --collect-only -q` green.

## Gate 2 — L1 units (rules)

- [x] Reserved name matcher: `CON`, `con.txt`, `COM1`, `LPT9`, `CON/readme.txt` → hit; `console.txt`, `conman/` → miss.
- [x] Illegal char matcher: each of `: * ? " < > |` → hit; safe chars → miss.
- [x] Trailing dot/space matcher (final and intermediate components).
- [x] Path length matcher (threshold configurable; invalid values rejected).
- [x] **Mutation sanity:** limiting the reserved-name check to the last component fails `test_reserved_name_hits`; restored.

## Gate 3 — L2 integration (fixture repos)

- [x] Fixture git repo with hostile paths across multiple refs → correct findings; refs listed per finding.
- [x] Baseline file suppresses known-existing (plain list and `--json` report formats).
- [x] Config-aware severity: rule set to `warn` → exit 0; set to `error` → exit 1; invalid config → exit 2.

## Gate 4 — L3 e2e (live)

- [ ] Live audit of a large real repo on host → correct findings. (Fixture audit passes.)
- [x] SARIF output validated against the SARIF 2.1.0 JSON schema (`jsonschema`, 2026-10-25).
- [x] `--dry-run` lists rules without scanning.

## Gate 5 — L5 adversarial

- [x] Empty repo → clean exit 0.
- [x] Non-git dir → clean `E_GIT` (exit 3).
- [ ] Huge repo (100k+ commits) → bounded memory. (Only a 500-file synthetic smoke and a small `--history` fixture were run.)
- [ ] Invalid UTF-8 path bytes → surrogateescape, no crash. (Non-ASCII paths and cp1252 stdout are tested; raw invalid bytes are not.)

## Gate 6 — Report-only & honesty audit (pre-M8)

- [x] Test: zero writes to the audited repository during a scan (HEAD and `git status` unchanged; no write commands in source).
- [x] README states report-only; no rewrite claims; non-goals explicit.
- [x] No TODO/FIXME in src/.
- [x] Secrets scan clean: `detect-secrets` on all tracked files → 0 findings. Full git history was not separately scanned.

## Gate 7 — L4 clean env

- [x] Fresh venv → wheel install → CLI scan of a fixture repo green (`--history`, JSON + SARIF written).
- [x] README quickstart verbatim-tested from a fresh clone (2026-10-25): venv, `pip install .`, `pathgate scan` → exit 0.

## Gate 8 — Packaging (G3-gated; do NOT run without operator approval)

- [x] Wheel built (`pip wheel` and `python -m build`).
- [x] sdist built; `twine check` passed for wheel and sdist.
- [x] PyPI lookup returned 404 on 2026-10-25 (name unregistered at check time; re-check before publishing).
- [ ] Publish ONLY at G3 with trusted publishing (OIDC), after G2 checklist.

## Definition of done (v0.1)

Gates 0–5 + 7 + 6 (items 1–3) green with evidence in PROGRESS.md. Gate 8 prepared but not executed. History mode = v0.5 if Gate 0 perf fails target.
