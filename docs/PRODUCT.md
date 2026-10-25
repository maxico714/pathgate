# PRODUCT — pathgate

Status: SCAFFOLD (not built). Date: 2026-10-12.

## Problem

Repos shared across Windows and Linux often contain Windows-hostile paths (illegal characters, reserved names, trailing dots/spaces, 260+ char paths). Windows clones fail or silently mangle them; CI on Windows breaks; contributors on Windows are locked out. Existing checks (`pre-commit-hooks`) only inspect **staged** changes — history and other refs are unaudited. Manual procedures (Atlassian / Bamboo KBs) don't scale. Teams need a CI-friendly auditor that reads git objects directly across all refs and history, with severity they can tune.

## Target users (personas)

1. **Cross-platform OSS maintainer (primary):** repo used by Windows + Linux contributors; Windows clone issues in issues. Job: audit all refs + history before the next release; block regressions in CI.
2. **Monorepo platform engineer (secondary):** huge repo; Windows dev fleet. Job: CI gate on path legality; SARIF for code-scanning UI.
3. **Security / compliance reviewer (tertiary):** needs audit trail of path decisions. Job: JSON/SARIF artifacts + exit codes.

## Jobs-to-be-done

- "Scan all refs + full history for Windows-hostile paths; no checkout."
- "Fail CI only on `error` severity; warn on the rest."
- "Give me SARIF for GitHub code-scanning; JSON for my scripts."

## Value proposition (one sentence)

CI-friendly git auditor that finds Windows-hostile paths across all refs and history **without checkout** — SARIF + JSON, config-aware severity, report-only.

## Non-goals (explicit)

- **Never rewrites history or working tree** (rewriting = separate human-gated tool, post-1.0 at earliest).
- Not a general git linter (no commit-message, no branch-name checks in v1).
- Not a Windows-path *fixer* (report only; human fixes).
- Not real-time (one-shot CLI / CI step).

## MVP scope (MoSCoW)

**Must (v0.1 walking skeleton):**
- Rules: reserved names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`9`, `LPT1`–`9`); illegal chars (`: * ? " < > |`); trailing dot/space; path length (>260 warn, >config error).
- **All-refs-tips-first**: `git for-each-ref` + `ls-tree -r` per ref tip; aggregate findings.
- Config-aware severity: YAML config mapping rule → error / warn / info; defaults documented.
- Output: human report + `--json` + `--sarif`; exit codes (error → non-zero).
- `--dry-run` (list rules, no scan); `doctor` self-check.

**Should (v0.5):**
- Full history opt-in (`--history`): `rev-list --all` + `ls-tree` with **tree-OID dedup** + progress bar (perf budget [UNKNOWN] — Gate 0 spike measures).
- Baseline file (`.pathgate-baseline`) to suppress known-existing findings; new findings only.
- GitHub Action wrapper.

**Could (v1.0):**
- Configurable length threshold; path normalization (case-insensitive on Windows); PR diff mode (new paths only).

**Won't (this run):** history rewrite; commit-message lint; branch-name lint; auto-fix.

## Success criteria (measurable)

| Criterion | Measure | Command/proof |
|---|---|---|
| L1 units | Rule matchers (reserved, illegal char, trailing, length) unit tests green | `pytest -q` |
| L2 integration | Fixture git repo (bare) with hostile paths → correct findings across refs | `pytest tests/integration/` |
| L3 e2e | Live audit of a real repo on host (p2/p1 or clone) → correct findings; SARIF valid | `pathgate scan --sarif out.sarif` |
| L4 clean env | Fresh clone + `pip install -e .` + fixture tests green | README steps in CI |
| L5 adversarial | Empty repo → clean exit 0; huge repo → progress + bounded memory; non-git dir → clean error | tests/adversarial/ |
| Report-only | Zero writes to git objects / working tree (code review + CI audit) | `pytest tests/security/` |
| Honesty | No rewrite claims; README states report-only | manual review |

## Honest comparison

- **pre-commit-hooks path checks:** staged-only; we audit all refs + history.
- **4 partials (Jul–Sep 2026):** one-off scripts; none ship all-refs + history + SARIF + config-aware severity together.
- **Manual procedures (Atlassian/Bamboo KBs):** don't scale; we automate.
- **git-for-windows#4005:** documents the pain; no tool owns the audit.

## Naming & license

- Name `pathgate` — free on PyPI + npm (verified 2026-10-11); re-check at G2.
- License: MIT.

## Risk register (top)

| Risk | Sev | Mitigation |
|---|---|---|
| History scan too slow on huge repos | High | Gate 0 perf spike; tree-OID dedup; progress; all-refs default, history opt-in |
| False positives annoy | Med | Config-aware severity; baseline file |
| Scope creep to rewrite | High | Report-only enforced in code + CI; README non-goals |
| git plumbing changes | Med | Thin CLI wrapper; pin git version in README |
