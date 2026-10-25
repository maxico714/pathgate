# ROADMAP — pathgate

Status: v0.1 implemented and locally verified 2026-10-25; not published. SemVer; Keep a Changelog. Report-only (no rewrite).

## v0.1 — Walking skeleton

- [ ] Gate 0: perf spike — all-refs-tips on a real repo (p2/p1 or clone); history with tree-OID dedup on same repo; log wall times + findings in DECISIONS.md. If history > 5 min → history stays experimental / opt-in only.
- [x] Rules: reserved name, illegal char, trailing dot/space, path length (any path component for the name and trailing checks).
- [x] All-refs-tips audit (`for-each-ref` + `ls-tree -r`).
- [x] Config-aware severity (YAML, validated); human + `--json` + `--sarif` reporters.
- [x] Exit codes; `doctor`; README quickstart.
- [ ] CI workflow and green matrix (no `.github/workflows` yet).

**Riskiest assumption to spike first:** history-scan performance. Already in Gate 0.

## v0.5 — Core value

- [x] History opt-in (`--history`) with tree-OID dedup (single `git log` call; no progress bar; large-repo performance still unmeasured).
- [x] Baseline file (suppress known-existing; accepts a plain list or a `--json` report).
- [ ] GitHub Action wrapper; SARIF validated against GitHub code-scanning schema.

## v1.0 — Production-ready

- [x] Configurable length threshold. Case-insensitive normalization option and PR diff mode remain open.
- [x] L4 clean-environment verification (fresh venv + wheel). SBOM and signed releases (G3) remain open.
- [ ] THIRD_PARTY_NOTICES; name free on PyPI confirmed.

## Post-1.0 (parked)

- History rewrite tool (separate, human-gated — explicitly out of scope for pathgate core).
- Commit-message / branch-name lint (separate tool).

## Maintenance cadence

- git plumbing changes = thin CLI wrapper patch.
- Rule defaults = data/config (minor).
