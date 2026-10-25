# ROADMAP — pathgate

Status: SCAFFOLD. SemVer; Keep a Changelog. Report-only (no rewrite).

## v0.1 — Walking skeleton

- [ ] Gate 0: perf spike — all-refs-tips on a real repo (p2/p1 or clone); history with tree-OID dedup on same repo; log wall times + findings in DECISIONS.md. If history > 5 min → history stays experimental / opt-in only.
- [ ] Rules: reserved name, illegal char, trailing dot/space, path length.
- [ ] All-refs-tips audit (`for-each-ref` + `ls-tree -r`).
- [ ] Config-aware severity (YAML); human + `--json` + `--sarif` reporters.
- [ ] Exit codes; `doctor`; README quickstart; CI green.

**Riskiest assumption to spike first:** history-scan performance. Already in Gate 0.

## v0.5 — Core value

- [ ] History opt-in (`--history`) with tree-OID dedup + progress (if Gate 0 perf acceptable).
- [ ] Baseline file (suppress known-existing; new findings only).
- [ ] GitHub Action wrapper; SARIF validated against GitHub code-scanning schema.

## v1.0 — Production-ready

- [ ] Configurable length threshold; case-insensitive normalization option; PR diff mode (new paths only).
- [ ] L4 clean-env verification; SBOM; signed releases (G3).
- [ ] THIRD_PARTY_NOTICES; name free on PyPI confirmed.

## Post-1.0 (parked)

- History rewrite tool (separate, human-gated — explicitly out of scope for pathgate core).
- Commit-message / branch-name lint (separate tool).

## Maintenance cadence

- git plumbing changes = thin CLI wrapper patch.
- Rule defaults = data/config (minor).
