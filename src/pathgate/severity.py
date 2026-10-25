"""Severity resolution and configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .rules import DEFAULT_RULES, Rule, RuleId

DEFAULT_MAX_PATH = 260


class Severity(str, Enum):
    ERROR = "error"
    WARN = "warn"
    INFO = "info"


class ConfigError(ValueError):
    """Raised when a pathgate configuration file is invalid."""


DEFAULT_CONFIG: dict[str, Any] = {
    "rules": {
        "RESERVED_NAME": "error",
        "ILLEGAL_CHAR": "error",
        "TRAILING_DOT_SPACE": "error",
        "PATH_LENGTH": {"severity": "warn", "max": DEFAULT_MAX_PATH},
    },
    "baseline": None,
}


@dataclass(frozen=True)
class RuleConfig:
    severity: Severity
    params: dict[str, Any] = field(default_factory=dict)


def load_config(path: Path | None) -> dict[str, Any]:
    """Load config from a YAML file, merged over the defaults."""
    config: dict[str, Any] = {**DEFAULT_CONFIG, "rules": dict(DEFAULT_CONFIG["rules"])}
    if not path or not path.exists():
        return config

    try:
        with path.open("r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as err:
        raise ConfigError(f"cannot read config {path}: {err}") from err

    if not isinstance(user, dict):
        raise ConfigError(f"config {path} must be a YAML mapping")

    user_rules = user.get("rules")
    if user_rules is not None:
        if not isinstance(user_rules, dict):
            raise ConfigError(f"config {path}: 'rules' must be a mapping")
        config["rules"] = {**DEFAULT_CONFIG["rules"], **user_rules}

    if "baseline" in user:
        baseline = user["baseline"]
        if baseline is not None and not isinstance(baseline, str):
            raise ConfigError(f"config {path}: 'baseline' must be a path string")
        config["baseline"] = baseline

    return config


def _coerce_severity(value: Any, rule_key: str) -> Severity:
    if isinstance(value, Severity):
        return value
    if isinstance(value, str):
        try:
            return Severity(value.strip().lower())
        except ValueError as err:
            raise ConfigError(
                f"invalid severity {value!r} for rule {rule_key}; expected error, warn or info"
            ) from err
    raise ConfigError(
        f"invalid severity {value!r} for rule {rule_key}; expected error, warn or info"
    )


def resolve_severity(rule: Rule, config: dict[str, Any]) -> RuleConfig:
    """Resolve the severity and params for a rule from config."""
    rule_key = rule.id.value
    rule_cfg = config.get("rules", {}).get(rule_key, rule.default_severity)
    if isinstance(rule_cfg, dict):
        severity = _coerce_severity(rule_cfg.get("severity", rule.default_severity), rule_key)
        params = {k: v for k, v in rule_cfg.items() if k != "severity"}
        return RuleConfig(severity=severity, params=params)
    return RuleConfig(severity=_coerce_severity(rule_cfg, rule_key))


def resolve_max_path(config: dict[str, Any]) -> int:
    """Return the validated PATH_LENGTH.max value."""
    rule = next(r for r in DEFAULT_RULES if r.id is RuleId.PATH_LENGTH)
    raw = resolve_severity(rule, config).params.get("max", DEFAULT_MAX_PATH)
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        raise ConfigError(f"invalid PATH_LENGTH.max {raw!r}; expected a positive integer")
    return raw
