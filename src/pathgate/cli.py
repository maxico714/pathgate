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
    log_all_commit_trees,
    ls_tree_recursive_full,
)
from .report import Finding, ScanResult, Summary, render_human, render_json, render_sarif
from .rules import DEFAULT_RULES, RuleId, check_all
from .severity import (
    ConfigError,
    Severity,
    load_config,
    resolve_max_path,
    resolve_severity,
)


def _configure_console() -> None:
    """Avoid UnicodeEncodeError when stdout is redirected to a legacy codepage."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="backslashreplace")


def _scan_refs(
    repo: Path,
    refs: list[Ref],
    config: dict[str, Any],
    baseline: set[tuple[str, str]],
) -> tuple[list[Finding], set[str], int]:
    findings_map: dict[tuple[str, RuleId], Finding] = {}
    seen_paths: set[str] = set()
    failures = 0
    max_len = resolve_max_path(config)
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
            failures += 1
            print(f"warning: failed to scan ref {ref.name}: {e}", file=sys.stderr)
    return list(findings_map.values()), seen_paths, failures


def _scan_history(
    repo: Path, config: dict[str, Any], baseline: set[tuple[str, str]]
) -> tuple[list[Finding], set[str], int]:
    findings_map: dict[tuple[str, RuleId], Finding] = {}
    seen_trees: set[str] = set()
    seen_paths: set[str] = set()
    failures = 0
    max_len = resolve_max_path(config)
    for commit_oid, tree_oid in log_all_commit_trees(repo):
        if tree_oid in seen_trees:
            continue
        seen_trees.add(tree_oid)
        short = commit_oid[:8]
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
            failures += 1
            print(f"warning: failed to scan tree {tree_oid[:8]}: {e}", file=sys.stderr)
    return list(findings_map.values()), seen_paths, failures


def _load_baseline(path: Path | None) -> set[tuple[str, str]]:
    if not path or not path.exists():
        return set()
    import json

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # Accept both a plain list and pathgate's own scan --json report.
        items = data.get("findings") if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise ValueError("expected a list of findings")
        entries: set[tuple[str, str]] = set()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("baseline entries must be objects")
            entry_path = item["path"]
            entry_rule = item["rule"]
            if not isinstance(entry_path, str) or not isinstance(entry_rule, str):
                raise ValueError("baseline path and rule must be strings")
            entries.add((entry_path, entry_rule))
        return entries
    except (OSError, ValueError, TypeError, KeyError) as e:
        print(f"warning: ignoring unreadable baseline {path}: {e}", file=sys.stderr)
        return set()


def _print_rules(config: dict[str, Any]) -> None:
    print("pathgate rules (v1):")
    for rule in DEFAULT_RULES:
        severity = resolve_severity(rule, config).severity.value
        print(f"  {rule.id.value:24} {severity:5}  {rule.name}")


def main(argv: Sequence[str] | None = None) -> int:
    _configure_console()
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
    try:
        config = load_config(config_path)
        for rule in DEFAULT_RULES:
            resolve_severity(rule, config)
        resolve_max_path(config)
    except ConfigError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    effective_config_path = config_path if config_path.exists() else None
    baseline_path = args.baseline
    if baseline_path is None and config.get("baseline"):
        baseline_path = repo / str(config["baseline"])
    baseline = _load_baseline(baseline_path)

    if args.command == "rules":
        _print_rules(config)
        return 0

    if args.command == "doctor":
        print(f"git: {get_git_version()}")
        if not is_git_repo(repo):
            print(f"error: {repo} is not a git repository", file=sys.stderr)
            return 3
        try:
            refs = list_all_refs(repo)
        except GitError as err:
            print(f"error: cannot list refs: {err}", file=sys.stderr)
            return 4
        print(f"repo: {repo}")
        print(f"refs: {len(refs)}")
        print("doctor: ready")
        return 0

    if args.command == "scan":
        if not is_git_repo(repo):
            print(f"error: {repo} is not a git repository", file=sys.stderr)
            return 3

        if args.dry_run:
            _print_rules(config)
            return 0

        start = time.perf_counter()
        try:
            refs = list_all_refs(repo)
        except GitError as err:
            print(f"error: cannot list refs: {err}", file=sys.stderr)
            return 4
        findings, scanned_paths, failures = _scan_refs(repo, refs, config, baseline)
        scanned_refs = len(refs)

        if args.history:
            try:
                history_findings, history_paths, history_failures = _scan_history(
                    repo, config, baseline
                )
            except GitError as err:
                print(f"error: cannot read history: {err}", file=sys.stderr)
                return 4
            failures += history_failures
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
        try:
            if args.json:
                args.json.write_text(render_json(result, effective_config_path), encoding="utf-8")
                print(f"JSON report: {args.json}", file=sys.stderr)
            if args.sarif:
                args.sarif.write_text(
                    render_sarif(result, effective_config_path, config), encoding="utf-8"
                )
                print(f"SARIF report: {args.sarif}", file=sys.stderr)
        except OSError as err:
            print(f"error: cannot write report: {err}", file=sys.stderr)
            return 4

        if failures:
            print(
                f"error: {failures} read(s) failed; results are incomplete",
                file=sys.stderr,
            )
            return 4

        return Summary(
            errors=sum(1 for f in findings if f.severity == Severity.ERROR),
            warnings=sum(1 for f in findings if f.severity == Severity.WARN),
            infos=sum(1 for f in findings if f.severity == Severity.INFO),
        ).exit_code

    return 2


if __name__ == "__main__":
    sys.exit(main())
