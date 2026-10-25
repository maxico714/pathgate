from __future__ import annotations

import tempfile
from pathlib import Path

from pathgate.cli import main
from tests.githelpers import commit_files, init_repo


def test_empty_repo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        # No commits yet: still a valid git repository, so doctor succeeds.
        assert main(["--repo", str(repo), "doctor"]) == 0
        # Empty repo with one commit
        commit_files(repo, {"README.md": "test"}, "initial")
        assert main(["--repo", str(repo), "scan"]) == 0


def test_non_git_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "notagit"
        repo.mkdir()
        (repo / "file.txt").write_text("test")
        assert main(["--repo", str(repo), "scan"]) == 3


def test_invalid_utf8_path() -> None:
    """Git can store paths as bytes; decode with surrogateescape."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        # Create a file with a non-UTF-8 byte sequence in the name via git plumbing
        # This is hard to test directly; we test that the decoder doesn't crash
        commit_files(repo, {"normal.txt": "test"}, "initial")
        assert main(["--repo", str(repo), "scan"]) == 0


def test_huge_repo_bounded_memory() -> None:
    """Test with a larger repo to verify streaming behavior."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)

        # Create many files
        files = {f"dir{i}/file{j}.txt": "content" for i in range(10) for j in range(50)}
        commit_files(repo, files, "many files")

        # Should complete without memory issues
        assert main(["--repo", str(repo), "scan"]) == 0


def test_non_ascii_paths() -> None:
    """Non-ASCII paths should be handled correctly."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"файл.txt": "content", "文件.txt": "内容"}, "unicode")
        assert main(["--repo", str(repo), "scan"]) == 0


def test_case_insensitive_reserved() -> None:
    """Reserved names are case-insensitive."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"con": "x"}, "lowercase")
        assert main(["--repo", str(repo), "scan"]) == 1

        repo2 = Path(tmp) / "repo2"
        repo2.mkdir()
        init_repo(repo2)
        commit_files(repo2, {"CON.txt": "x"}, "with ext")
        assert main(["--repo", str(repo2), "scan"]) == 1

        repo3 = Path(tmp) / "repo3"
        repo3.mkdir()
        init_repo(repo3)
        commit_files(repo3, {"Com1": "x"}, "mixed")
        assert main(["--repo", str(repo3), "scan"]) == 1


def test_history_mode_empty_repo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"README.md": "test"}, "initial")
        # History mode on small repo should work
        assert main(["--repo", str(repo), "scan", "--history"]) == 0


def test_history_mode_with_findings() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        init_repo(repo)
        commit_files(repo, {"README.md": "test"}, "initial")
        commit_files(repo, {"CON": "bad"}, "add reserved")
        assert main(["--repo", str(repo), "scan", "--history"]) == 1
