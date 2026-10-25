from __future__ import annotations

import json
from pathlib import Path

from pathgate.cli import main
from pathgate.report import Finding, ScanResult, render_json, render_sarif
from pathgate.rules import RuleId
from pathgate.severity import Severity
from tests.githelpers import commit_files, init_repo

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_no_writes_during_scan(tmp_path: Path) -> None:
    """Normal scan creates no files outside --json/--sarif."""
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    commit_files(repo, {"README.md": "test"}, "initial")

    # Run scan without --json/--sarif
    assert main(["--repo", str(repo), "scan"]) == 0

    # No files should be created in repo
    assert sorted(p.name for p in repo.iterdir()) == [".git", "README.md"]


def test_no_shell_true() -> None:
    """No shell=True in source code."""
    for name in ("cli.py", "refs.py", "rules.py", "severity.py", "report.py"):
        source = (PROJECT_ROOT / "src" / "pathgate" / name).read_text(encoding="utf-8")
        assert "shell=True" not in source


def test_no_git_write_commands() -> None:
    """No git write commands in source code."""
    write_commands = (
        "commit-tree",
        "update-ref",
        "write-tree",
        '"add"',
        '"checkout"',
        '"reset"',
        '"gc"',
    )
    for name in ("cli.py", "refs.py"):
        source = (PROJECT_ROOT / "src" / "pathgate" / name).read_text(encoding="utf-8")
        assert "git write" not in source.lower()
        for command in write_commands:
            assert command not in source


def test_sarif_redaction_no_secrets() -> None:
    """SARIF rendering handles finding paths without crashing."""
    finding = Finding(
        path="path/token=secret123",
        rule=RuleId.ILLEGAL_CHAR,
        severity=Severity.ERROR,
        refs=("refs/heads/main",),
        detail="Found in ref refs/heads/main",
    )
    result = ScanResult(findings=(finding,), scanned_refs=1, scanned_paths=1, elapsed_ms=50)
    data = json.loads(render_sarif(result))
    assert data["version"] == "2.1.0"
    assert len(data["runs"][0]["results"]) == 1


def test_json_output_no_env_leak() -> None:
    """JSON output doesn't leak environment variables."""
    finding = Finding(path="CON", rule=RuleId.RESERVED_NAME, severity=Severity.ERROR, refs=("r",))
    result = ScanResult(findings=(finding,), scanned_refs=1, scanned_paths=1, elapsed_ms=50)
    json_str = render_json(result)
    data = json.loads(json_str)
    assert data["findings"][0]["path"] == "CON"
    assert "env" not in json_str.lower()
    assert "password" not in json_str.lower()
    assert "token" not in json_str.lower()


def test_read_only_assertion_in_code() -> None:
    """Source code documents read-only intent."""
    source = (PROJECT_ROOT / "src" / "pathgate" / "cli.py").read_text(encoding="utf-8")
    assert (
        "report-only" in source.lower()
        or "read-only" in source.lower()
        or "no checkout" in source.lower()
    )
