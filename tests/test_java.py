"""Tests for scripts/utils/java.py."""

# ruff: noqa: S101, S105
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scripts.utils.java import JavaRunner, run_java


class TestJavaRunner:
    def test_build_env_clears_github_repo(self) -> None:
        with patch.dict("os.environ", {"GITHUB_REPOSITORY": "test/repo", "OTHER": "value"}):
            runner = JavaRunner()
            env = runner._build_env()
            assert "GITHUB_REPOSITORY" not in env
            assert env["OTHER"] == "value"

    def test_build_env_preserves_keystore_passwords(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "RV_KEYSTORE_PASSWORD": "pass1",
                "RV_KEYSTORE_ENTRY_PASSWORD": "pass2",
            },
        ):
            runner = JavaRunner()
            env = runner._build_env()
            assert env["RV_KEYSTORE_PASSWORD"] == "pass1"
            assert env["RV_KEYSTORE_ENTRY_PASSWORD"] == "pass2"

    def test_build_env_custom_env_updates(self) -> None:
        runner = JavaRunner(env={"CUSTOM": "var"})
        env = runner._build_env()
        assert env["CUSTOM"] == "var"

    @patch("subprocess.run")
    def test_run_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["java", "args"],
            returncode=0,
            stdout="success",
            stderr="",
        )
        runner = JavaRunner()
        result = runner.run(["some", "args"])
        assert result.returncode == 0
        assert result.stdout == "success"
        expected_cmd = ["java"] + runner.java_args + ["some", "args"]
        mock_run.assert_called_once_with(
            expected_cmd,
            env=runner._build_env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=None,
        )

    @patch("subprocess.run")
    def test_run_failure_returncode(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["java", "args"],
            returncode=1,
            stdout="",
            stderr="error",
        )
        runner = JavaRunner()
        result = runner.run(["some", "args"])
        assert result.returncode == 1
        assert result.stderr == "error"

    @patch("subprocess.run")
    def test_run_file_not_found(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError("java not found")
        runner = JavaRunner()
        with pytest.raises(OSError, match="Java executable not found in PATH"):
            runner.run(["args"])

    @patch("subprocess.run")
    def test_run_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["java"], timeout=10)
        runner = JavaRunner()
        with pytest.raises(subprocess.TimeoutExpired):
            runner.run(["args"], timeout=10)

    @patch("scripts.utils.java.JavaRunner.run")
    def test_run_jar(self, mock_run: MagicMock) -> None:
        runner = JavaRunner()
        runner.run_jar("app.jar", ["arg1", "arg2"])
        mock_run.assert_called_once_with(["-jar", "app.jar", "arg1", "arg2"], timeout=None)


@patch("subprocess.run")
def test_run_java_convenience(mock_run: MagicMock) -> None:
    """Test the run_java convenience function."""
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    run_java(["arg1"], timeout=30)
    assert mock_run.call_args.kwargs["timeout"] == 30
    assert "arg1" in mock_run.call_args.args[0]
