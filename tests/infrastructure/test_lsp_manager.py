"""Tests for LspManager."""

import unittest

from src.infrastructure.lsp.lsp_manager import (
    LspManager,
    LspServerConfig,
)


class TestLspManager(unittest.TestCase):

    def test_status_shows_uninstalled_servers(self):
        config = LspServerConfig(
            name="fake-server",
            command=["fake-server", "--stdio"],
            languages=["fakeland"],
            binary="definitely-not-installed-binary-xyz",
        )
        manager = LspManager(configs=[config])
        status = manager.status()

        self.assertIn("fake-server", status)
        self.assertFalse(status["fake-server"]["running"])
        self.assertFalse(status["fake-server"]["installed"])

    def test_boot_skips_missing_binaries(self):
        config = LspServerConfig(
            name="missing",
            command=["nonexistent-binary"],
            languages=["nope"],
            binary="nonexistent-binary",
        )
        manager = LspManager(configs=[config])
        results = manager.boot()
        manager.shutdown()

        self.assertFalse(results["missing"])

    def test_get_server_returns_none_for_unknown_lang(self):
        manager = LspManager(configs=[])
        self.assertIsNone(manager.get_server("python"))

    def test_shutdown_is_idempotent(self):
        manager = LspManager(configs=[])
        manager.shutdown()
        manager.shutdown()  # should not raise


if __name__ == "__main__":
    unittest.main()
