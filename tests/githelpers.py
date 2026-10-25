"""Git test fixtures that can store Windows-hostile paths.

Git for Windows refuses to index or import paths such as ``CON``, ``file:name.txt``
or a 261-character name, and the filesystem refuses to create them. The tool under
test reads git objects, so these helpers build trees with ``mktree`` and never rely
on the working tree. Benign files are also written to disk so tests can assert that
a scan does not modify the repository.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run(repo: Path, *args: str, input_text: str | None = None) -> str:
    data = input_text.encode("utf-8") if input_text is not None else None
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        input=data,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    return proc.stdout.decode("utf-8", "surrogateescape")


def init_repo(repo: Path, branch: str = "main") -> None:
    subprocess.run(
        ["git", "init", "-q", "-b", branch, str(repo)],
        check=True,
        capture_output=True,
    )
    _run(repo, "config", "user.email", "test@test")
    _run(repo, "config", "user.name", "Test")


def _write_benign(repo: Path, name: str, content: str) -> None:
    try:
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError:
        pass  # Windows rejects this name; it still exists in the git tree


def _build_tree(repo: Path, entries: dict[str, tuple[str, str]]) -> str:
    files = {name: value for name, value in entries.items() if "/" not in name}
    dirs: dict[str, dict[str, tuple[str, str]]] = {}
    for name, value in entries.items():
        if "/" in name:
            head, rest = name.split("/", 1)
            dirs.setdefault(head, {})[rest] = value

    lines = [f"{mode} blob {oid}\t{name}" for name, (mode, oid) in sorted(files.items())]
    for name, sub in sorted(dirs.items()):
        lines.append(f"040000 tree {_build_tree(repo, sub)}\t{name}")
    return _run(repo, "mktree", input_text="\n".join(lines) + "\n").strip()


def _existing_entries(repo: Path, branch: str) -> dict[str, tuple[str, str]]:
    """Return path -> (mode, oid) for the current tip of ``branch``, if any."""
    tip = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        capture_output=True,
        text=True,
    )
    if tip.returncode != 0:
        return {}
    out = _run(repo, "ls-tree", "-r", "-z", "--full-tree", tip.stdout.strip())
    entries: dict[str, tuple[str, str]] = {}
    for record in out.split("\0"):
        if not record:
            continue
        header, _, path = record.partition("\t")
        mode, _type, oid = header.split(" ", 2)
        entries[path] = (mode, oid)
    return entries


def commit_files(repo: Path, files: dict[str, str], msg: str = "msg", branch: str = "main") -> str:
    """Create a commit containing ``files``, including names Windows rejects."""
    entries = _existing_entries(repo, branch)
    for name, content in files.items():
        proc = subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
            input=content.encode("utf-8"),
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode(errors="replace"))
        entries[name] = ("100644", proc.stdout.decode().strip())
        _write_benign(repo, name, content)

    tree = _build_tree(repo, entries)
    parent = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        capture_output=True,
        text=True,
    )
    args = ["commit-tree", tree]
    if parent.returncode == 0 and parent.stdout.strip():
        args += ["-p", parent.stdout.strip()]
    args += ["-m", msg]
    commit = _run(repo, *args).strip()
    _run(repo, "update-ref", f"refs/heads/{branch}", commit)
    return commit
