"""Infrastructure: shell command execution."""

from __future__ import annotations

import subprocess

from src.domain.ports.command_runner import CommandRunner


class ShellCommandRunner(CommandRunner):
    """Runs shell commands via subprocess."""

    def run(self, cmd: str, dry_run: bool = False) -> tuple[bool, str]:
        if dry_run:
            return True, f"[DRY RUN] {cmd}"
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=120,
            )
            output = result.stdout + result.stderr
            return result.returncode == 0, output.strip()
        except subprocess.TimeoutExpired:
            return False, "Command timed out after 120s"
        except Exception as e:
            return False, str(e)
