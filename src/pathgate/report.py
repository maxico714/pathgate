"""Reporters: human, JSON, SARIF."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .rules import DEFAULT_RULES, RuleId
from .severity import Severity


@dataclass(frozen=True)
class Finding:
    path: str
    rule: RuleId
    severity: Severity
    refs: tuple[str, ...]
    detail: str = ""


@dataclass(frozen=True)
class ScanResult:
    findings: tuple[Finding, ...]
    scanned_refs: int
    scanned_paths: int
    elapsed_ms: int


@dataclass(frozen=True)
class Summary:
    errors: int
    warnings: int
    infos: int

    @property
    def exit_code(self) -> int:
        if self.errors:
            return 1
        return 0


def summarize(findings: tuple[Finding, ...]) -> Summary:
    errors = sum(1 for f in findings if f.severity == Severity.ERROR)
    warnings = sum(1 for f in findings if f.severity == Severity.WARN)
    infos = sum(1 for f in findings if f.severity == Severity.INFO)
    return Summary(errors=errors, warnings=warnings, infos=infos)


def render_human(result: ScanResult, config_path: Path | None = None) -> str:
    summary = summarize(result.findings)
    lines = [
        (
            f"pathgate {result.scanned_refs} refs, "
            f"{result.scanned_paths} paths, {result.elapsed_ms} ms"
        ),
        f"config: {config_path or 'defaults'}",
        "",
    ]
    if not result.findings:
        lines.append("No Windows-hostile paths found.")
    else:
        for f in result.findings:
            lines.append(f"  [{f.severity.value.upper():5}] {f.rule.value}: {f.path}")
            if f.refs:
                lines.append(f"         refs: {', '.join(f.refs)}")
        lines.extend(
            [
                "",
                (
                    f"Summary: {summary.errors} error(s), "
                    f"{summary.warnings} warning(s), {summary.infos} info"
                ),
            ]
        )
    return "\n".join(lines)


def render_json(result: ScanResult, config_path: Path | None = None) -> str:
    summary = summarize(result.findings)
    payload = {
        "tool": "pathgate",
        "version": "0.1.0",
        "scanned_refs": result.scanned_refs,
        "scanned_paths": result.scanned_paths,
        "elapsed_ms": result.elapsed_ms,
        "config": str(config_path) if config_path else "defaults",
        "findings": [
            {
                "path": f.path,
                "rule": f.rule.value,
                "severity": f.severity.value,
                "refs": list(f.refs),
                "detail": f.detail,
            }
            for f in result.findings
        ],
        "summary": {
            "errors": summary.errors,
            "warnings": summary.warnings,
            "infos": summary.infos,
            "exit_code": summary.exit_code,
        },
    }
    return json.dumps(payload, indent=2)


def render_sarif(result: ScanResult, config_path: Path | None = None) -> str:
    runs = [
        {
            "tool": {
                "driver": {
                    "name": "pathgate",
                    "version": "0.1.0",
                    "informationUri": "https://github.com/<owner>/pathgate",
                    "rules": [
                        {
                            "id": rule.id.value,
                            "name": rule.name,
                            "shortDescription": {"text": rule.description},
                            "defaultConfiguration": {"level": rule.default_severity},
                        }
                        for rule in DEFAULT_RULES
                    ],
                }
            },
            "results": [
                {
                    "ruleId": f.rule.value,
                    "level": {"error": "error", "warn": "warning", "info": "note"}[
                        f.severity.value
                    ],
                    "message": {"text": f.path},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": f.path},
                            }
                        }
                    ],
                }
                for f in result.findings
            ],
        }
    ]
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": runs,
    }
    return json.dumps(sarif, indent=2)
