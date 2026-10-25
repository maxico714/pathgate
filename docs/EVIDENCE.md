# EVIDENCE — pathgate (verified research summary)

Source: round-3 M2 verifier V-W + skeptic-r3 + gap-evidence-r3. Ledger row 38. ADR-003. Access dates 2026-10-11.

## Gap class: A sliver / F adjacent

- **pre-commit-hooks** path checks: **staged-only** (misses history and other refs) — named partial.
- **4 partials (Jul–Sep 2026):** various one-off scripts; none ship all-refs + history + SARIF + config-aware severity together.
- **git-for-windows#4005:** documents the Windows-hostile path pain; no tool owns the audit.
- **Atlassian / Bamboo KBs:** manual audit procedures; don't scale.

## Demand hook: 4/5

- Real artifacts: git-for-windows#4005; Atlassian/Bamboo KBs; cross-platform monorepo pain documented across issues.
- Hook sentence: "Windows-hostile paths break clones; pre-commit-hooks only check staged files — here is the all-refs + history auditor with SARIF, no checkout, report-only."
- Cap reason (D-006): pain is real but niche (cross-platform repos); no single viral post.

## Host feasibility: VERIFIED (2026-10-12 spike)

- `git` on host (full path `C:\Program Files\Git\cmd\git.exe`); read-only plumbing (`ls-tree`, `rev-list`, `for-each-ref`) smoke-tested.
- **Perf spike (synthetic 200-file, 10-commit repo, 2026-10-12):** all-refs-tips ls-tree = 80 ms (200 paths) ✓; history with tree-OID dedup = 1579 ms (PowerShell per-commit subprocess ~160ms/commit — Python batched single-subprocess `git log --all --name-only` needed for large repos, likely 10-50x faster). All-refs-tips budget confirmed; history [UNKNOWN] mitigated by batching strategy.
- Python 3.12 on host; no Docker needed (L4-lite fallback).
- Name `pathgate` free on PyPI + npm (re-confirmed 2026-10-12 live checks).

## Correction ledger

| Claim | Verified fact |
|---|---|
| "pre-commit-hooks covers history" | FALSE — staged-only |
| "History scan is fast" | [UNKNOWN] — perf budget unmeasured; Gate 0 spike mandatory |
| "No partials exist" | FALSE — 4 partials Jul–Sep 2026; none complete (class F adjacent, not pure A) |

## Skeptic failure scenarios → binding mitigations

1. History scan too slow on huge repos → Gate 0 perf spike; tree-OID dedup; all-refs default, history opt-in.
2. False positives annoy → config-aware severity; baseline file.
3. Scope creep to rewrite → report-only enforced in code + CI; README non-goals.
4. git plumbing changes → thin CLI wrapper; pin git version in README.

## Pre-mortem: "2027-04 pathgate failed"

History too slow / git-for-windows shipped a native check / false-positives annoyed / scope creep to rewrite broke trust → mitigation: perf spike first, report-only posture, config severity + baseline, thin wrapper.

## Score: 65/105 (round-3 runner-up; ADR-003 fallback). SURVIVE with conditions: all-refs-tips-first, history perf spike, config-aware severity, SARIF+JSON, report-only no rewrite.
