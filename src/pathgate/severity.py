"""Severity resolution and configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .rules import Rule


class Severity(str, Enum):
    ERROR = "error"
    WARN = "warn"
    INFO = "info"


DEFAULT_CONFIG: dict[str, Any] = {
    "rules": {
        "RESERVED_NAME": "error",
        "ILLEGAL_CHAR": "error",
        "TRAILING_DOT_SPACE": "error",
        "PATH_LENGTH": {"severity": "warn", "max": 260},
    },
    "baseline": None,
}


@dataclass(frozen=True)
class RuleConfig:
    severity: Severity
    params: dict[str, Any] = field(default_factory=dict)


def load_config(path: Path | None) -> dict[str, Any]:
    """Load config from YAML file, merging with defaults."""
    config: dict[str, Any] = {**DEFAULT_CONFIG}
    if path and path.exists():
        with path.open("r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
        if isinstance(user, dict):
            # Deep merge for rules
            user_rules = user.get("rules")
            if isinstance(user_rules, dict):
                config["rules"] = {**DEFAULT_CONFIG["rules"], **user_rules}
            if "baseline" in user:
                config["baseline"] = user["baseline"]
    return config


def resolve_severity(rule: Rule, config: dict[str, Any]) -> RuleConfig:
    """Resolve the severity and params for a rule from config."""
    rule_key = rule.id.value
    rule_cfg = config.get("rules", {}).get(rule_key, rule.default_severity)
    if isinstance(rule_cfg, dict):
        severity = Severity(rule_cfg.get("severity", rule.default_severity))
        params = {k: v for k, v in rule_cfg.items() if k != "severity"}
        return RuleConfig(severity=severity, params=params)
    else:
        return RuleConfig(severity=Severity(rule_cfg))
