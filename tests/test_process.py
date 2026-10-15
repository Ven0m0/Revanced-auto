"""Tests for process utility functions."""

# ruff: noqa: S101

from scripts.utils.process import sample_job


def test_sample_job() -> None:
    """Test sample_job multiplies value by 2."""
    assert sample_job(2) == 4
    assert sample_job(-3) == -6
    assert sample_job(0) == 0
