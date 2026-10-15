#!/usr/bin/env python3
"""Java subprocess management module for running Java-based tools."""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

JAVA_ARGS = [
    # Deterministic UTF-8 output regardless of host locale/console codepage
    # (stdout.encoding/stderr.encoding are the JDK 18+ supported properties;
    # captured subprocess output would default to these anyway, but pinning
    # them keeps behavior identical across JDK versions and OSes).
    "-Dfile.encoding=UTF-8",
    "-Dstdout.encoding=UTF-8",
    "-Dstderr.encoding=UTF-8",
    "-Duser.language=en",
    "-Duser.country=US",
    # No GUI is ever used; avoids any accidental AWT/headful init.
    "-Djava.awt.headless=true",
    # Throughput over latency: each invocation is a short batch job, not a
    # long-lived server, so pause-time-optimized G1 buys nothing here.
    "-XX:+UseParallelGC",
    # Scale the heap to the machine/container instead of the JVM's 25%
    # default -- this process usually runs alone (or a couple in parallel
    # via the build's ThreadPoolExecutor), so it can safely claim most of
    # available memory for speed while still leaving headroom.
    "-XX:MaxRAMPercentage=75.0",
    # Fail fast and loud on OOM instead of hanging until the caller's
    # subprocess timeout fires.
    "-XX:+ExitOnOutOfMemoryError",
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

    java_args: list[str] = field(default_factory=JAVA_ARGS.copy)
    env: dict[str, str] | None = None
    timeout: int | None = None
    _base_env: dict[str, str] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._base_env = os.environ.copy()

    def _build_env(self) -> dict[str, str]:
        """Build the subprocess environment: base env, minus GITHUB_REPOSITORY, plus overrides."""
        env = self._base_env.copy()
        env.pop("GITHUB_REPOSITORY", None)

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
                check=False,
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
