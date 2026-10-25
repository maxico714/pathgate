"""Command-line interface for pathgate."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .refs import (
    GitError,
    Ref,
    get_git_version,
    is_git_repo,
    list_all_refs,
    ls_tree_recursive_full,
    rev_list_all,
)
from .report import Finding, ScanResult, Summary, render_human, render_json, render_sarif
from .rules import DEFAULT_RULES, RuleId, check_all
from .severity import Severity, load_config, resolve_severity

_PATH_LENGTH_RULE = next(r for r in DEFAULT_RULES if r.id is RuleId.PATH_LENGTH)


def _max_path_len(config: dict[str, Any]) -> int:
    raw = resolve_severity(_PATH_LENGTH_RULE, config).params.get("max", 260)
    return raw if isinstance(raw, int) and raw > 0 else 260


def _scan_refs(
    repo: Path,
    refs: list[Ref],
    config: dict[str, Any],
    baseline: set[tuple[str, str]],
) -> tuple[list[Finding], set[str]]:
    findings_map: dict[tuple[str, RuleId], Finding] = {}
    seen_paths: set[str] = set()
    max_len = _max_path_len(config)
    for ref in refs:
        try:
            for entry in ls_tree_recursive_full(repo, ref.oid):
                path = entry.path
                seen_paths.add(path)
                hits = check_all(path, max_len)
                for rule in DEFAULT_RULES:
                    if not hits.get(rule.id, False):
                        continue
                    if (path, rule.id.value) in baseline:
                        continue
                    rule_cfg = resolve_severity(rule, config)
                    key = (path, rule.id)
                    existing = findings_map.get(key)
                    new_refs = (ref.name,) if not existing else existing.refs + (ref.name,)
                    findings_map[key] = Finding(
                        path=path,
                        rule=rule.id,
                        severity=rule_cfg.severity,
                        refs=new_refs,
                        detail=f"Found in ref {ref.name}",
                    )
        except GitError as e:
            # Continue on individual ref errors, warn in detail
            print(f"warning: failed to scan ref {ref.name}: {e}", file=sys.stderr)
    return list(findings_map.values()), seen_paths


def _scan_history(
    repo: Path, config: dict[str, Any], baseline: set[tuple[str, str]]
) -> tuple[list[Finding], set[str]]:
    from .refs import get_tree_oid_for_commit

    findings_map: dict[tuple[str, RuleId], Finding] = {}
    seen_trees: set[str] = set()
    seen_paths: set[str] = set()
    max_len = _max_path_len(config)
    commits = rev_list_all(repo)
    for commit_oid in commits:
        try:
            tree_oid = get_tree_oid_for_commit(repo, commit_oid)
        except GitError:
            continue
        if tree_oid in seen_trees:
            continue
        seen_trees.add(tree_oid)
        try:
            for entry in ls_tree_recursive_full(repo, tree_oid):
                path = entry.path
                seen_paths.add(path)
                hits = check_all(path, max_len)
                for rule in DEFAULT_RULES:
                    if not hits.get(rule.id, False):
                        continue
                    if (path, rule.id.value) in baseline:
                        continue
                    rule_cfg = resolve_severity(rule, config)
                    key = (path, rule.id)
                    short = commit_oid[:8]
                    ref_label = f"commit:{short}"
                    existing = findings_map.get(key)
                    new_refs = (ref_label,) if not existing else existing.refs + (ref_label,)
                    findings_map[key] = Finding(
                        path=path,
                        rule=rule.id,
                        severity=rule_cfg.severity,
                        refs=new_refs,
                        detail=f"Found in commit {short}",
                    )
        except GitError as e:
            print(f"warning: failed to scan commit {commit_oid[:8]}: {e}", file=sys.stderr)
    return list(findings_map.values()), seen_paths


def _load_baseline(path: Path | None) -> set[tuple[str, str]]:
    if not path or not path.exists():
        return set()
    import json

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {(item["path"], item["rule"]) for item in data}
    except (OSError, ValueError, TypeError, KeyError) as e:
        print(f"warning: ignoring unreadable baseline {path}: {e}", file=sys.stderr)
        return set()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pathgate",
        description=(
            "Audit git refs and history for Windows-hostile paths: "
            "no checkout, report-only, SARIF + JSON"
        ),
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    parser.add_argument(
        "--repo", type=Path, default=Path.cwd(), help="Git repository to audit (default: cwd)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="YAML config file (default: .pathgate.yaml in repo)",
    )
    parser.add_argument(
        "--baseline", type=Path, default=None, help="Baseline JSON file to suppress known findings"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Scan repository for Windows-hostile paths")
    scan.add_argument("--history", action="store_true", help="Scan full history (opt-in, slower)")
    scan.add_argument("--json", type=Path, default=None, help="Write JSON report to file")
    scan.add_argument("--sarif", type=Path, default=None, help="Write SARIF report to file")
    scan.add_argument(
        "--baseline",
        type=Path,
        default=argparse.SUPPRESS,
        help="Baseline JSON file to suppress known findings",
    )
    scan.add_argument("--dry-run", action="store_true", help="List rules without scanning")

    rules_cmd = sub.add_parser("rules", help="Inspect rules")
    rules_sub = rules_cmd.add_subparsers(dest="rules_command", required=True)
    rules_sub.add_parser("list", help="List rules with default severity")

    sub.add_parser("doctor", help="Self-check: git availability, repo validity")

    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    config_path = args.config or (repo / ".pathgate.yaml")
    config = load_config(config_path)
    effective_config_path = config_path if config_path.exists() else None
    baseline_path = args.baseline
    if baseline_path is None and config.get("baseline"):
        baseline_path = repo / str(config["baseline"])
    baseline = _load_baseline(baseline_path)

    if args.command == "rules":
        print("pathgate rules (v1):")
        for rule in DEFAULT_RULES:
            rule_cfg = config.get("rules", {}).get(rule.id.value, rule.default_severity)
            if isinstance(rule_cfg, dict):
                sev = rule_cfg.get("severity", rule.default_severity)
            else:
                sev = rule_cfg
            print(f"  {rule.id.value:24} {sev:5}  {rule.name}")
        return 0

    if args.command == "doctor":
        print(f"git: {get_git_version()}")
        if not is_git_repo(repo):
            print(f"error: {repo} is not a git repository", file=sys.stderr)
            return 3
        refs = list_all_refs(repo)
        print(f"repo: {repo}")
        print(f"refs: {len(refs)}")
        print("doctor: ready")
        return 0

    if args.command == "scan":
        if not is_git_repo(repo):
            print(f"error: {repo} is not a git repository", file=sys.stderr)
            return 3

        if args.dry_run:
            print("pathgate rules (v1):")
            for rule in DEFAULT_RULES:
                rule_cfg = config.get("rules", {}).get(rule.id.value, rule.default_severity)
                if isinstance(rule_cfg, dict):
                    sev = rule_cfg.get("severity", rule.default_severity)
                else:
                    sev = rule_cfg
                print(f"  {rule.id.value:24} {sev:5}  {rule.name}")
            return 0

        start = time.perf_counter()
        refs = list_all_refs(repo)
        findings, scanned_paths = _scan_refs(repo, refs, config, baseline)
        scanned_refs = len(refs)

        if args.history:
            history_findings, history_paths = _scan_history(repo, config, baseline)
            scanned_paths |= history_paths
            existing = {(f.path, f.rule): f for f in findings}
            for hf in history_findings:
                key = (hf.path, hf.rule)
                if key in existing:
                    merged = Finding(
                        path=hf.path,
                        rule=hf.rule,
                        severity=existing[key].severity,
                        refs=existing[key].refs + hf.refs,
                        detail=f"{existing[key].detail}; {hf.detail}",
                    )
                    existing[key] = merged
                else:
                    existing[key] = hf
            findings = list(existing.values())

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        result = ScanResult(
            findings=tuple(findings),
            scanned_refs=scanned_refs,
            scanned_paths=len(scanned_paths),
            elapsed_ms=elapsed_ms,
        )

        # Output
        print(render_human(result, effective_config_path))
        if args.json:
            args.json.write_text(render_json(result, effective_config_path), encoding="utf-8")
            print(f"JSON report: {args.json}", file=sys.stderr)
        if args.sarif:
            args.sarif.write_text(render_sarif(result, effective_config_path), encoding="utf-8")
            print(f"SARIF report: {args.sarif}", file=sys.stderr)

        return Summary(
            errors=sum(1 for f in findings if f.severity == Severity.ERROR),
            warnings=sum(1 for f in findings if f.severity == Severity.WARN),
            infos=sum(1 for f in findings if f.severity == Severity.INFO),
        ).exit_code

    return 2


if __name__ == "__main__":
    sys.exit(main())
