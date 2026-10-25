# BUILD CHECKLIST — pathgate

Status: SCAFFOLD. Work top-to-bottom; each gate shows REAL command output. Circuit breaker: 3 failures per gate → stop, re-research, log in STATE.md.

## Gate 0 — Perf spike (riskiest assumption FIRST) — **PARTIALLY DONE 2026-10-12**

Spike results (synthetic repo: 200 files, 10 commits, PowerShell subprocess per git call):
- `for-each-ref`: 75 ms (1 ref)
- `rev-list --all`: 79 ms (10 commits)
- `all-refs-tips ls-tree`: **80 ms** (200 paths at tips) — well within 60s budget ✓
- `history ls-tree + tree-OID dedup`: **1579 ms** (10 unique trees, 1100 paths) — ~160ms/commit subprocess overhead in PowerShell

**Verdict:** all-refs-tips mode confirmed fast. History mode: PowerShell per-commit subprocess is too slow for 10k+ commits (~27min extrapolated); **Python implementation must use single-subprocess `git log --all --name-only --pretty=format:`** (not per-commit ls-tree) — likely 10-50x faster. [UNKNOWN] remains for huge repos (100k+ commits) — re-measure with Python batched approach at build time.

- [ ] Re-run spike with Python single-subprocess batched git-log approach; log wall time + findings in DECISIONS.md. If still > 5 min on a real mid-size repo → history stays experimental / opt-in only.

## Gate 1 — L0 static (every commit)

- [ ] `ruff check .` + `ruff format --check .` clean.
- [ ] `mypy src/` clean.
- [ ] `pytest --collect-only -q` green.

## Gate 2 — L1 units (rules)

- [ ] Reserved name matcher: `CON`, `con.txt`, `COM1`, `LPT9` → hit; `console.txt` → miss.
- [ ] Illegal char matcher: each of `: * ? " < > |` → hit; safe chars → miss.
- [ ] Trailing dot/space matcher.
- [ ] Path length matcher (threshold configurable).
- [ ] **Mutation sanity:** flip case-insensitive off for reserved names → `con.txt` test MUST fail; restore.

## Gate 3 — L2 integration (fixture repos)

- [ ] Fixture bare git repo with hostile paths across multiple refs → correct findings; refs listed per finding.
- [ ] Baseline file suppresses known-existing; new finding still reported.
- [ ] Config-aware severity: rule set to `info` → exit 0; set to `error` → exit 1.

## Gate 4 — L3 e2e (live)

- [ ] Live audit of real repo on host (p2/p1 or clone) → correct findings; SARIF valid (validate against SARIF 2.1.0 schema or GitHub code-scanning).
- [ ] `--dry-run` lists rules without scanning.

## Gate 5 — L5 adversarial

- [ ] Empty repo → clean exit 0.
- [ ] Non-git dir → clean `E_GIT` (exit 3).
- [ ] Huge repo → progress + bounded memory (stream, not buffer).
- [ ] Invalid UTF-8 path → surrogateescape, no crash.

## Gate 6 — Report-only & honesty audit (pre-M8)

- [ ] CI test: zero writes to git objects / working tree (no `write-tree`, no `update-ref`, no file writes outside temp).
- [ ] README states report-only; no rewrite claims; non-goals explicit.
- [ ] No TODO/FIXME in src/.
- [ ] Secrets scan clean.

## Gate 7 — L4 clean env

- [ ] Fresh clone → `pip install -e .` → fixture tests green on clean machine profile.
- [ ] README quickstart verbatim-tested.

## Gate 8 — Packaging (G3-gated; do NOT run without operator approval)

- [ ] `python -m build` → wheel + sdist; `twine check` clean.
- [ ] Name free on PyPI confirmed live (re-check `pathgate`).
- [ ] Publish ONLY at G3 with trusted publishing (OIDC), after G2 checklist.

## Definition of done (v0.1)

Gates 0–5 + 7 + 6 (items 1–3) green with evidence in PROGRESS.md. Gate 8 prepared but not executed. History mode = v0.5 if Gate 0 perf fails target.
