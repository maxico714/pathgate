"""Windows-hostile path rules and matchers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePath
from re import Pattern

# Windows reserved names (case-insensitive)
_RESERVED_BASENAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)

# Illegal characters in Windows paths
_ILLEGAL_CHARS = frozenset([":", "*", "?", '"', "<", ">", "|"])

# Pattern for trailing dot or space
_TRAILING_DOT_SPACE_RE: Pattern[str] = re.compile(r"[. ]$")


class RuleId(str, Enum):
    RESERVED_NAME = "RESERVED_NAME"
    ILLEGAL_CHAR = "ILLEGAL_CHAR"
    TRAILING_DOT_SPACE = "TRAILING_DOT_SPACE"
    PATH_LENGTH = "PATH_LENGTH"


@dataclass(frozen=True)
class Rule:
    id: RuleId
    name: str
    default_severity: str  # "error" | "warn" | "info"
    description: str


# Default rule definitions
DEFAULT_RULES: tuple[Rule, ...] = (
    Rule(
        id=RuleId.RESERVED_NAME,
        name="Windows reserved name",
        default_severity="error",
        description=(
            "Path basename (case-insensitive) matches a Windows reserved device name "
            "(CON, PRN, AUX, NUL, COM1–9, LPT1–9) with or without extension."
        ),
    ),
    Rule(
        id=RuleId.ILLEGAL_CHAR,
        name="Illegal character in path",
        default_severity="error",
        description='Path contains a character illegal on Windows: : * ? " < > |',
    ),
    Rule(
        id=RuleId.TRAILING_DOT_SPACE,
        name="Trailing dot or space",
        default_severity="error",
        description="Path ends with a dot (.) or space ( ), which Windows rejects.",
    ),
    Rule(
        id=RuleId.PATH_LENGTH,
        name="Path length exceeds limit",
        default_severity="warn",
        description="Path length exceeds the configured maximum (default 260).",
    ),
)


def check_reserved_name(path: str) -> bool:
    """Return True if the path's basename matches a Windows reserved name."""
    basename = PurePath(path).name
    # Split on first dot to handle extensions like CON.txt
    name_part = basename.split(".", 1)[0].upper()
    return name_part in _RESERVED_BASENAMES


def check_illegal_char(path: str) -> bool:
    """Return True if the path contains any Windows-illegal character."""
    return any(ch in _ILLEGAL_CHARS for ch in path)


def check_trailing_dot_space(path: str) -> bool:
    """Return True if the path ends with a dot or space."""
    return bool(_TRAILING_DOT_SPACE_RE.search(path))


def check_path_length(path: str, max_len: int = 260) -> bool:
    """Return True if the path length exceeds max_len."""
    return len(path) > max_len


def check_all(path: str, max_len: int = 260) -> dict[RuleId, bool]:
    """Run all rule checks on a path. Returns dict of RuleId -> hit."""
    return {
        RuleId.RESERVED_NAME: check_reserved_name(path),
        RuleId.ILLEGAL_CHAR: check_illegal_char(path),
        RuleId.TRAILING_DOT_SPACE: check_trailing_dot_space(path),
        RuleId.PATH_LENGTH: check_path_length(path, max_len),
    }
