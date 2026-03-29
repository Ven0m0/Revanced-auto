#!/usr/bin/env python3
"""Java subprocess management module for running Java-based tools."""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

JAVA_ARGS = [
    "-Dfile.encoding=UTF-8",
    "-Duser.country=US",
    "-Duser.language=en",
    "-Dsun.stdout.encoding=UTF-8",
    "-Dsun.stderr.encoding=UTF-8",
    "-XX:+UseParallelGC",
    "-XX:+AggressiveOpts",
    "-XX:+UseStringDeduplication",
    "-XX:+IgnoreUnrecognizedVMOptions",
]


@dataclass
class JavaRunner:
    """Manages JVM arguments and subprocess execution for Java tools.

    Attributes:
        java_args: List of JVM arguments passed to the Java process.
        env: Custom environment variables for the subprocess.
        timeout: Maximum time in seconds for the subprocess to complete.

    Example:
        >>> runner = JavaRunner()
        >>> result = runner.run(["-jar", "cli.jar", "patch", "input.apk"])
        >>> print(result.returncode)
        0
    """

    java_args: list[str] = field(default_factory=lambda: JAVA_ARGS.copy())
    env: dict[str, str] | None = None
    timeout: int | None = None

    def __post_init__(self) -> None:
        self._base_env = os.environ.copy()

    def _build_env(self) -> dict[str, str]:
        """Build the environment for the subprocess.

        Returns:
            Dictionary of environment variables with GITHUB_REPOSITORY cleared
            and keystore passwords added if available.
        """
        env = self._base_env.copy()

        env.pop("GITHUB_REPOSITORY", None)

        if "RV_KEYSTORE_PASSWORD" in env:
            env["RV_KEYSTORE_PASSWORD"] = env["RV_KEYSTORE_PASSWORD"]
        if "RV_KEYSTORE_ENTRY_PASSWORD" in env:
            env["RV_KEYSTORE_ENTRY_PASSWORD"] = env["RV_KEYSTORE_ENTRY_PASSWORD"]

        if self.env:
            env.update(self.env)

        return env

    def run(self, args: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
        """Run a Java subprocess with the given arguments.

        Args:
            args: Command-line arguments to pass to the Java executable.
            timeout: Maximum time in seconds for the subprocess to complete.
                Overrides the instance timeout if set.

        Returns:
            CompletedProcess instance with returncode, stdout, and stderr.

        Raises:
            OSError: If the java executable is not found.
            subprocess.TimeoutExpired: If the subprocess times out.
        """
        cmd = ["java"] + self.java_args + args
        exec_env = self._build_env()

        logger.info("Executing: java %s", " ".join(self.java_args + args))

        try:
            result = subprocess.run(
                cmd,
                env=exec_env,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
            )
            logger.debug("Return code: %d", result.returncode)
            if result.stdout:
                logger.debug("stdout: %s", result.stdout)
            if result.stderr:
                logger.debug("stderr: %s", result.stderr)
            return result
        except FileNotFoundError as e:
            logger.error("Java executable not found: %s", e)
            raise OSError("Java executable not found in PATH") from e
        except subprocess.TimeoutExpired as e:
            logger.error("Java subprocess timed out after %s seconds", e.timeout)
            raise

    def run_jar(
        self,
        jar_path: str,
        jar_args: list[str],
        *,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a JAR file with the given arguments.

        Args:
            jar_path: Path to the JAR file to execute.
            jar_args: Arguments to pass to the JAR file.
            timeout: Maximum time in seconds for the subprocess to complete.

        Returns:
            CompletedProcess instance with returncode, stdout, and stderr.
        """
        return self.run(["-jar", jar_path] + jar_args, timeout=timeout)


def run_java(args: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Convenience function to run a Java subprocess.

    Args:
        args: Command-line arguments to pass to the Java executable.
        timeout: Maximum time in seconds for the subprocess to complete.

    Returns:
        CompletedProcess instance with returncode, stdout, and stderr.
    """
    runner = JavaRunner(timeout=timeout)
    return runner.run(args)
