"""Git ref enumeration and tree walking using git plumbing commands."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Ref:
    name: str
    oid: str


@dataclass(frozen=True)
class TreeEntry:
    path: str
    mode: str
    oid: str


class GitError(Exception):
    """Raised when a git command fails."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"git {' '.join(cmd)} failed ({returncode}): {stderr.strip()}")


def _run_git(repo: Path, args: list[str]) -> str:
    """Run a git command in the repo and return stdout. Raises GitError on failure."""
    cmd = ["git", "-C", str(repo), *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            check=False,
            timeout=120.0,
        )
    except FileNotFoundError as err:
        raise GitError(cmd, -1, "git executable not found") from err
    except subprocess.TimeoutExpired as err:
        raise GitError(cmd, -1, "timeout") from err
    if proc.returncode != 0:
        raise GitError(cmd, proc.returncode, proc.stderr)
    return proc.stdout


def list_all_refs(repo: Path) -> list[Ref]:
    """Return all refs (branches, tags) with their OIDs."""
    out = _run_git(repo, ["for-each-ref", "--format=%(refname) %(objectname)"])
    refs = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        refname, oid = line.split(" ", 1)
        refs.append(Ref(name=refname, oid=oid))
    return refs


def ls_tree_recursive(repo: Path, tree_ish: str) -> Iterator[TreeEntry]:
    """Yield all paths in a tree-ish recursively using ls-tree -r."""
    out = _run_git(repo, ["ls-tree", "-r", "-z", "--name-only", "--full-tree", tree_ish])
    for path in out.split("\0"):
        if not path:
            continue
        yield TreeEntry(path=path, mode="", oid="")


def ls_tree_recursive_full(repo: Path, tree_ish: str) -> Iterator[TreeEntry]:
    """Yield all tree entries with mode, oid, path using ls-tree -r (full format)."""
    # -z keeps raw paths: no C-style quoting for unicode or special characters.
    out = _run_git(repo, ["ls-tree", "-r", "-z", "--full-tree", tree_ish])
    for record in out.split("\0"):
        if not record:
            continue
        # Format: mode type oid\tpath
        parts = record.split("\t", 1)
        if len(parts) != 2:
            continue
        header, path = parts
        mode_type_oid = header.split(" ")
        if len(mode_type_oid) >= 3:
            mode = mode_type_oid[0]
            oid = mode_type_oid[2]
            yield TreeEntry(path=path, mode=mode, oid=oid)


def rev_list_all(repo: Path) -> list[str]:
    """Return all commit OIDs in history (rev-list --all)."""
    out = _run_git(repo, ["rev-list", "--all"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def get_tree_oid_for_commit(repo: Path, commit_oid: str) -> str:
    """Get the tree OID for a commit."""
    out = _run_git(repo, ["rev-parse", f"{commit_oid}^{{tree}}"])
    return out.strip()


def is_git_repo(path: Path) -> bool:
    """Check if path is a git repository."""
    try:
        _run_git(path, ["rev-parse", "--git-dir"])
        return True
    except GitError:
        return False


def get_git_version() -> str:
    """Return git version string."""
    try:
        proc = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout.strip()
    except FileNotFoundError:
        return "not found"
