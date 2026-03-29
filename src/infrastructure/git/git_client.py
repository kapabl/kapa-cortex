"""Infrastructure: git operations via subprocess."""

from __future__ import annotations

import subprocess

from src.domain.entity.changed_file import ChangedFile
from src.domain.port.git_reader import GitReader


class GitClient(GitReader):
    """Implements GitReader via subprocess git commands."""

    def current_branch(self) -> str:
        return self._run("rev-parse", "--abbrev-ref", "HEAD")

    def detect_base(self) -> str:
        """Auto-detect the base branch (main, master, develop)."""
        for candidate in ("main", "master", "develop"):
            for ref in (candidate, f"origin/{candidate}"):
                try:
                    self._run("rev-parse", "--verify", ref)
                    return candidate
                except RuntimeError:
                    continue
        return "main"

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


