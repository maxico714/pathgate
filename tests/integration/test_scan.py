from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pathgate.cli import main
from pathgate.report import (
    Finding,
    ScanResult,
    Summary,
    render_human,
    render_json,
    render_sarif,
    summarize,
)
from pathgate.rules import DEFAULT_RULES, RuleId
from pathgate.severity import Severity, load_config, resolve_severity
from tests.githelpers import commit_files, init_repo


def test_severity_resolution_defaults() -> None:
    config = {"rules": {}}
    for rule in DEFAULT_RULES:
        rc = resolve_severity(rule, config)
        assert rc.severity == Severity(rule.default_severity)


def test_severity_resolution_override() -> None:
    config = {"rules": {"RESERVED_NAME": "warn"}}
    rule = next(r for r in DEFAULT_RULES if r.id.value == "RESERVED_NAME")
    rc = resolve_severity(rule, config)
    assert rc.severity == Severity.WARN


def test_severity_resolution_with_params() -> None:
    config = {"rules": {"PATH_LENGTH": {"severity": "error", "max": 300}}}
    rule = next(r for r in DEFAULT_RULES if r.id.value == "PATH_LENGTH")
    rc = resolve_severity(rule, config)
    assert rc.severity == Severity.ERROR
    assert rc.params.get("max") == 300


def test_load_config_merges() -> None:
    import yaml

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"rules": {"RESERVED_NAME": "info"}}, f)
        path = Path(f.name)
    try:
        config = load_config(path)
        assert config["rules"]["RESERVED_NAME"] == "info"
        assert config["rules"]["ILLEGAL_CHAR"] == "error"  # default preserved
    finally:
        path.unlink()


def test_scan_empty_repo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"README.md": "# Test"}, "initial")

        assert main(["--repo", str(repo), "doctor"]) == 0
        assert main(["--repo", str(repo), "scan", "--dry-run"]) == 0
        assert main(["--repo", str(repo), "scan"]) == 0  # no findings


def test_scan_finds_reserved_name() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"CON": "content"}, "add reserved")
        commit_files(repo, {"normal.txt": "ok"}, "add normal")

        assert main(["--repo", str(repo), "scan"]) == 1  # error severity


def test_scan_finds_illegal_char() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"file:name.txt": "content"}, "add illegal")

        assert main(["--repo", str(repo), "scan"]) == 1


def test_scan_finds_trailing_dot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"file.": "content"}, "add trailing dot")

        assert main(["--repo", str(repo), "scan"]) == 1


def test_scan_finds_trailing_space() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"file ": "content"}, "add trailing space")

        assert main(["--repo", str(repo), "scan"]) == 1


def test_severity_warn_does_not_fail() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        long_name = "a" * 261
        commit_files(repo, {long_name: "content"}, "long path")

        # PATH_LENGTH default is warn
        assert main(["--repo", str(repo), "scan"]) == 0


def test_config_override_makes_length_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        long_name = "a" * 261
        commit_files(repo, {long_name: "content"}, "long path")
        config = repo / ".pathgate.yaml"
        config.write_text(
            "rules:\n  PATH_LENGTH:\n    severity: error\n    max: 260\n", encoding="utf-8"
        )

        assert main(["--repo", str(repo), "scan"]) == 1


def test_config_path_length_severity_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"README.md": "ok"}, "initial")
        config = repo / ".pathgate.yaml"
        config.write_text("rules:\n  PATH_LENGTH: warn\n", encoding="utf-8")

        assert main(["--repo", str(repo), "scan"]) == 0


def test_invalid_severity_is_config_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"CON": "content"}, "add reserved")
        (repo / ".pathgate.yaml").write_text("rules:\n  RESERVED_NAME: fatal\n", encoding="utf-8")

        assert main(["--repo", str(repo), "scan"]) == 2


def test_malformed_config_is_config_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"README.md": "ok"}, "initial")
        (repo / ".pathgate.yaml").write_text("rules: [unclosed\n", encoding="utf-8")

        assert main(["--repo", str(repo), "scan"]) == 2


def test_non_mapping_rules_is_config_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"README.md": "ok"}, "initial")
        (repo / ".pathgate.yaml").write_text("rules: []\n", encoding="utf-8")

        assert main(["--repo", str(repo), "scan"]) == 2


def test_bool_or_string_max_is_config_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"README.md": "ok"}, "initial")
        for value in ("yes", '"300"', "0", "-5"):
            (repo / ".pathgate.yaml").write_text(
                f"rules:\n  PATH_LENGTH:\n    max: {value}\n", encoding="utf-8"
            )
            assert main(["--repo", str(repo), "scan"]) == 2, value


def test_uppercase_severity_accepted() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"CON": "content"}, "add reserved")
        (repo / ".pathgate.yaml").write_text("rules:\n  RESERVED_NAME: WARN\n", encoding="utf-8")

        assert main(["--repo", str(repo), "scan"]) == 0


def test_baseline_accepts_json_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"CON": "content"}, "add reserved")
        report = Path(tmp) / "report.json"

        assert main(["--repo", str(repo), "scan", "--json", str(report)]) == 1
        assert main(["--repo", str(repo), "scan", "--baseline", str(report)]) == 0


def test_sarif_encodes_artifact_uri() -> None:
    finding = Finding(
        path="a b#c?.txt",
        rule=RuleId.ILLEGAL_CHAR,
        severity=Severity.ERROR,
        refs=("refs/heads/main",),
    )
    result = ScanResult(findings=(finding,), scanned_refs=1, scanned_paths=1, elapsed_ms=1)
    data = json.loads(render_sarif(result))
    uri = data["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"][
        "uri"
    ]
    assert uri == "a%20b%23c%3F.txt"
    assert "informationUri" not in data["runs"][0]["tool"]["driver"]


def test_sarif_uses_valid_levels_and_config() -> None:
    result = ScanResult(findings=(), scanned_refs=0, scanned_paths=0, elapsed_ms=1)
    default = json.loads(render_sarif(result))
    rules = {r["id"]: r for r in default["runs"][0]["tool"]["driver"]["rules"]}
    assert rules["PATH_LENGTH"]["defaultConfiguration"]["level"] == "warning"
    assert rules["RESERVED_NAME"]["defaultConfiguration"]["level"] == "error"

    configured = json.loads(
        render_sarif(
            result,
            config={
                "rules": {
                    "PATH_LENGTH": "error",
                    "RESERVED_NAME": "info",
                }
            },
        )
    )
    rules = {r["id"]: r for r in configured["runs"][0]["tool"]["driver"]["rules"]}
    assert rules["PATH_LENGTH"]["defaultConfiguration"]["level"] == "error"
    assert rules["RESERVED_NAME"]["defaultConfiguration"]["level"] == "note"


def test_malformed_baseline_warns_and_scans() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"CON": "content"}, "add reserved")
        baseline = repo / "baseline.json"
        baseline.write_text("not json", encoding="utf-8")

        assert main(["--repo", str(repo), "scan", "--baseline", str(baseline)]) == 1


def test_config_baseline_suppresses() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"CON": "content"}, "add reserved")
        (repo / "baseline.json").write_text(
            json.dumps([{"path": "CON", "rule": "RESERVED_NAME"}]), encoding="utf-8"
        )
        (repo / ".pathgate.yaml").write_text("baseline: baseline.json\n", encoding="utf-8")

        assert main(["--repo", str(repo), "scan"]) == 0


def test_baseline_suppresses() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"CON": "content"}, "add reserved")
        baseline = repo / "baseline.json"
        baseline.write_text(
            json.dumps([{"path": "CON", "rule": "RESERVED_NAME"}]), encoding="utf-8"
        )

        assert main(["--repo", str(repo), "scan", "--baseline", str(baseline)]) == 0


def test_json_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"CON": "content"}, "add reserved")
        out = Path(tmp) / "out.json"

        assert main(["--repo", str(repo), "scan", "--json", str(out)]) == 1
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["summary"]["errors"] == 1
        assert data["scanned_paths"] == 1
        assert data["findings"][0]["rule"] == "RESERVED_NAME"
        assert data["findings"][0]["path"] == "CON"


def test_sarif_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"CON": "content"}, "add reserved")
        out = Path(tmp) / "out.sarif"

        assert main(["--repo", str(repo), "scan", "--sarif", str(out)]) == 1
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["version"] == "2.1.0"
        assert len(data["runs"][0]["results"]) == 1


def test_scan_multiple_refs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"main_file.txt": "content"}, "initial")
        commit_files(repo, {"CON": "bad"}, "bad on feature", branch="feature")
        out = Path(tmp) / "out.json"

        assert main(["--repo", str(repo), "scan", "--json", str(out)]) == 1
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["scanned_refs"] == 2
        assert data["scanned_paths"] == 2
        assert data["findings"][0]["refs"] == ["refs/heads/feature"]


def test_report_render_human() -> None:
    finding = Finding(
        path="CON",
        rule=RuleId.RESERVED_NAME,
        severity=Severity.ERROR,
        refs=("refs/heads/main",),
        detail="Found in ref refs/heads/main",
    )
    result = ScanResult(findings=(finding,), scanned_refs=1, scanned_paths=1, elapsed_ms=50)
    text = render_human(result)
    assert "CON" in text
    assert "RESERVED_NAME" in text
    assert "error" in text.lower()


def test_report_render_json() -> None:
    finding = Finding(
        path="CON",
        rule=RuleId.RESERVED_NAME,
        severity=Severity.ERROR,
        refs=("refs/heads/main",),
        detail="Found in ref refs/heads/main",
    )
    result = ScanResult(findings=(finding,), scanned_refs=1, scanned_paths=1, elapsed_ms=50)
    json_str = render_json(result)
    data = json.loads(json_str)
    assert data["summary"]["errors"] == 1
    assert data["findings"][0]["path"] == "CON"


def test_report_render_sarif() -> None:
    finding = Finding(
        path="CON",
        rule=RuleId.RESERVED_NAME,
        severity=Severity.ERROR,
        refs=("refs/heads/main",),
        detail="Found in ref refs/heads/main",
    )
    result = ScanResult(findings=(finding,), scanned_refs=1, scanned_paths=1, elapsed_ms=50)
    sarif_str = render_sarif(result)
    data = json.loads(sarif_str)
    assert data["version"] == "2.1.0"
    assert len(data["runs"][0]["results"]) == 1


def test_summary_exit_code() -> None:
    finding = Finding(path="CON", rule=RuleId.RESERVED_NAME, severity=Severity.ERROR, refs=("r",))
    result = ScanResult(findings=(finding,), scanned_refs=1, scanned_paths=1, elapsed_ms=50)
    assert Summary(errors=1, warnings=0, infos=0).exit_code == 1
    assert summarize(result.findings).exit_code == 1

    finding_w = Finding(path="long", rule=RuleId.PATH_LENGTH, severity=Severity.WARN, refs=("r",))
    result_w = ScanResult(findings=(finding_w,), scanned_refs=1, scanned_paths=1, elapsed_ms=50)
    assert summarize(result_w.findings).exit_code == 0
