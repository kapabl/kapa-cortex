"""Infrastructure: git operations via subprocess."""

from __future__ import annotations

import subprocess

from src.domain.entity.changed_file import ChangedFile
from src.domain.port.git_reader import GitReader


class GitClient(GitReader):
    """Implements GitReader via subprocess git commands."""

    def current_branch(self) -> str:
        return self._run("rev-parse", "--abbrev-ref", "HEAD")

    def resolve_base(self, base: str) -> str:
        for ref in [base, f"origin/{base}"]:
            try:
                self._run("rev-parse", "--verify", ref)
                return ref
            except RuntimeError:
                continue
        raise SystemExit(
            f"Error: base ref '{base}' not found. Try: git fetch origin {base}"
        )

    def merge_base(self, base_ref: str) -> str:
        return self._run("merge-base", base_ref, "HEAD")

    def file_source(self, path: str) -> str:
        try:
            return self._run("show", f"HEAD:{path}")
        except RuntimeError:
            return ""

    def diff_stat(self, base_ref: str) -> list[ChangedFile]:
        mb = self.merge_base(base_ref)
        return self._parse_diff(mb)

    def cochange_history(
        self, paths: list[str], max_commits: int = 200,
    ) -> dict[tuple[str, str], int]:
        return _analyze_cochange(paths, max_commits)

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed:\n{result.stderr}"
            )
        return result.stdout.strip()

    def _parse_diff(self, mb: str) -> list[ChangedFile]:
        raw = self._run("diff", "--numstat", "--diff-filter=ADMR", mb, "HEAD")
        if not raw:
            return []

        status_map = self._parse_name_status(mb)
        files: list[ChangedFile] = []

        for line in raw.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            added = int(parts[0]) if parts[0] != "-" else 0
            removed = int(parts[1]) if parts[1] != "-" else 0
            path = parts[2]
            diff_text = self._file_diff(mb, path)
            files.append(ChangedFile(
                path=path, added=added, removed=removed,
                status=status_map.get(path, "M"),
                diff_text=diff_text,
            ))
        return files

    def _parse_name_status(self, mb: str) -> dict[str, str]:
        raw = self._run("diff", "--name-status", "--diff-filter=ADMR", mb, "HEAD")
        result: dict[str, str] = {}
        for line in raw.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                result[parts[-1]] = parts[0][0]
        return result

    def _file_diff(self, mb: str, path: str) -> str:
        try:
            return self._run("diff", mb, "HEAD", "--", path)
        except RuntimeError:
            return ""


def _analyze_cochange(
    paths: list[str], max_commits: int,
) -> dict[tuple[str, str], int]:
    """Analyze git log for files that change together."""
    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={max_commits}",
             "--name-only", "--format="],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}

    path_set = set(paths)
    cochange: dict[tuple[str, str], int] = {}
    current_commit_files: list[str] = []

    for line in result.stdout.splitlines():
        if not line.strip():
            _count_pairs(current_commit_files, path_set, cochange)
            current_commit_files = []
        elif line.strip() in path_set:
            current_commit_files.append(line.strip())

    _count_pairs(current_commit_files, path_set, cochange)
    return cochange


def _count_pairs(
    files: list[str],
    path_set: set[str],
    cochange: dict[tuple[str, str], int],
) -> None:
    relevant = [f for f in files if f in path_set]
    for i, a in enumerate(relevant):
        for b in relevant[i + 1:]:
            pair = tuple(sorted([a, b]))
            cochange[pair] = cochange.get(pair, 0) + 1
