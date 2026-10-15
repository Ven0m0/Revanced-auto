"""Parallel job management module for running concurrent build tasks."""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

T = TypeVar("T")


@dataclass
class JobResult[T]:
    """Result of a job execution.

    Attributes:
        name: Name identifier for the job.
        success: Whether the job completed successfully.
        result: The return value from the job function.
        error: Error message if the job failed.
    """

    name: str
    success: bool
    result: T | None = None
    error: str | None = None


@dataclass
class JobStatus:
    """Tracks the status of a job.

    Attributes:
        name: Name identifier for the job.
        future: The future associated with this job.
    """

    name: str
    future: Any = field(default=None, init=False)


class JobRunner:
    """Manages concurrent job execution using process and thread pools.

    Supports CPU-bound tasks via ProcessPoolExecutor and I/O-bound tasks
    via ThreadPoolExecutor with optional async support.

    Attributes:
        max_workers: Maximum number of worker processes/threads.
        executor_type: The type of executor to use ('process' or 'thread').

    Example:
        >>> runner = JobRunner(max_workers=4)
        >>> runner.submit(build_function, args, name="YouTube-arm64")
        >>> results = runner.wait_all()
        >>> for result in results:
        ...     print(f"{result.name}: {'success' if result.success else 'failed'}")
    """

    def __init__(self, max_workers: int | None = None, executor_type: str = "process") -> None:
        """Initialize the JobRunner.

        Args:
            max_workers: Maximum number of workers. Defaults to CPU count.
            executor_type: Type of executor ('process' for CPU-bound, 'thread' for I/O-bound).
        """
        if max_workers is None:
            max_workers = os.cpu_count() or 1
        if max_workers < 1:
            msg = "max_workers must be at least 1"
            raise ValueError(msg)
        if executor_type not in ("process", "thread"):
            msg = "executor_type must be 'process' or 'thread'"
            raise ValueError(msg)

        self._max_workers = max_workers
        self._executor_type = executor_type
        self._executor: ProcessPoolExecutor | ThreadPoolExecutor | None = None
        self._jobs: dict[str, JobStatus] = {}

    def __enter__(self) -> Self:
        """Enter the context manager."""
        self._start_executor()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager and clean up resources."""
        self.shutdown(wait=True)

    def _start_executor(self) -> None:
        """Start the executor with configured settings."""
        if self._executor_type == "process":
            self._executor = ProcessPoolExecutor(max_workers=self._max_workers)
        else:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

    def submit(
        self,
        func: Callable[..., T],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        name: str | None = None,
    ) -> JobStatus:
        """Submit a job for execution.

        Args:
            func: The function to execute.
            args: Positional arguments to pass to the function.
            kwargs: Keyword arguments to pass to the function.
            name: Optional name identifier for the job.

        Returns:
            JobStatus object tracking the job.

        Raises:
            RuntimeError: If the runner is not started or is shut down.
        """
        if self._executor is None:
            msg = "JobRunner not started. Use the context manager before submitting jobs."
            raise RuntimeError(msg)

        if kwargs is None:
            kwargs = {}

        if name is None:
            name = f"job_{id(func)}_{len(self._jobs)}"

        if name in self._jobs:
            msg = f"Job with name '{name}' already exists."
            raise ValueError(msg)

        status = JobStatus(name=name)
        status.future = self._executor.submit(func, *args, **kwargs)
        self._jobs[name] = status

        return status

    def wait_all(self, timeout: float | None = None) -> list[JobResult[Any]]:
        """Wait for all submitted jobs to complete.

        Args:
            timeout: Maximum time to wait in seconds. None waits indefinitely.

        Returns:
            List of JobResult objects for all completed jobs.
        """
        if self._executor is None:
            return []

        results: list[JobResult[Any]] = []

        for name, status in self._jobs.items():
            if status.future is None:
                continue
            try:
                result = status.future.result(timeout=timeout)
                results.append(JobResult(name=name, success=True, result=result))
            except Exception as e:
                results.append(JobResult(name=name, success=False, error=str(e)))

        return results

    def shutdown(self, *, wait: bool = True) -> None:
        """Shutdown the executor and clean up resources.

        Args:
            wait: Whether to wait for pending jobs to complete.
        """
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None
        self._jobs.clear()

    @property
    def max_workers(self) -> int:
        """Maximum number of workers."""
        return self._max_workers

    @property
    def executor_type(self) -> str:
        """Type of executor ('process' or 'thread')."""
        return self._executor_type


def sample_job(value: int) -> int:
    """Sample job function for demonstration."""
    return value * 2


def main() -> int:
    """Run a simple demonstration of the JobRunner module."""
    parser = argparse.ArgumentParser(description="JobRunner demonstration")
    parser.add_argument("--workers", type=int, default=2, help="Number of workers")
    args = parser.parse_args()

    with JobRunner(max_workers=args.workers) as runner:
        for i in range(4):
            runner.submit(sample_job, (i,), name=f"job_{i}")

        results = runner.wait_all()
        for result in results:
            status = "success" if result.success else f"failed: {result.error}"
            print(f"{result.name}: {status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
