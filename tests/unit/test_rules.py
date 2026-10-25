from __future__ import annotations

from pathgate.rules import (
    DEFAULT_RULES,
    RuleId,
    check_all,
    check_illegal_char,
    check_path_length,
    check_reserved_name,
    check_trailing_dot_space,
)


def test_reserved_name_hits() -> None:
    assert check_reserved_name("CON")
    assert check_reserved_name("con")
    assert check_reserved_name("CON.txt")
    assert check_reserved_name("path/CON")
    assert check_reserved_name("path/con.txt")
    assert check_reserved_name("COM1")
    assert check_reserved_name("COM9")
    assert check_reserved_name("LPT1")
    assert check_reserved_name("LPT9")
    assert check_reserved_name("PRN")
    assert check_reserved_name("AUX")
    assert check_reserved_name("NUL")
    assert check_reserved_name("CON/readme.txt")
    assert check_reserved_name("path/CON/file.txt")
    assert check_reserved_name("aux/data.bin")


def test_reserved_name_misses() -> None:
    assert not check_reserved_name("console")
    assert not check_reserved_name("CONSOLE")
    assert not check_reserved_name("COMMON")
    assert not check_reserved_name("content")
    assert not check_reserved_name("normal.txt")
    assert not check_reserved_name("console/readme.txt")
    assert not check_reserved_name("path/conman/file.txt")


def test_illegal_char_hits() -> None:
    for ch in [":", "*", "?", '"', "<", ">", "|"]:
        assert check_illegal_char(f"path{ch}name")
        assert check_illegal_char(f"{ch}start")
        assert check_illegal_char(f"end{ch}")


def test_illegal_char_misses() -> None:
    assert not check_illegal_char("normal_path")
    assert not check_illegal_char("path.with.dots")
    assert not check_illegal_char("path-with-dashes")
    assert not check_illegal_char("path_with_underscores")


def test_trailing_dot_space_hits() -> None:
    assert check_trailing_dot_space("path.")
    assert check_trailing_dot_space("path ")
    assert check_trailing_dot_space("dir/. ")
    assert check_trailing_dot_space("file. ")
    assert check_trailing_dot_space("dir./file.txt")
    assert check_trailing_dot_space("dir /file.txt")
    assert check_trailing_dot_space("a/b./c")


def test_trailing_dot_space_misses() -> None:
    assert not check_trailing_dot_space("path")
    assert not check_trailing_dot_space("path.txt")
    assert not check_trailing_dot_space("dir/file")
    assert not check_trailing_dot_space("dir/.hidden/file")
    assert not check_trailing_dot_space("a/b.c/d")


def test_path_length_hits() -> None:
    long = "a" * 261
    assert check_path_length(long, 260)
    assert check_path_length(long, 100)


def test_path_length_misses() -> None:
    assert not check_path_length("short", 260)
    assert not check_path_length("a" * 260, 260)


def test_check_all() -> None:
    result = check_all("CON", 260)
    assert result[RuleId.RESERVED_NAME] is True
    assert result[RuleId.ILLEGAL_CHAR] is False
    assert result[RuleId.TRAILING_DOT_SPACE] is False
    assert result[RuleId.PATH_LENGTH] is False

    result = check_all("path:name", 260)
    assert result[RuleId.RESERVED_NAME] is False
    assert result[RuleId.ILLEGAL_CHAR] is True

    result = check_all("path.", 260)
    assert result[RuleId.TRAILING_DOT_SPACE] is True

    long = "a" * 261
    result = check_all(long, 260)
    assert result[RuleId.PATH_LENGTH] is True


def test_default_rules_complete() -> None:
    assert len(DEFAULT_RULES) == 4
    ids = {r.id for r in DEFAULT_RULES}
    assert ids == {
        RuleId.RESERVED_NAME,
        RuleId.ILLEGAL_CHAR,
        RuleId.TRAILING_DOT_SPACE,
        RuleId.PATH_LENGTH,
    }
    for rule in DEFAULT_RULES:
        assert rule.name
        assert rule.default_severity in ("error", "warn", "info")
        assert rule.description
