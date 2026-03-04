"""Test suite for APKPure search parser."""

from __future__ import annotations

import argparse

import pytest

from scripts.apkpure_search import (
    APKPURE_BASE,
    AppConfig,
    Command,
    ParseResult,
    URLBuilder,
    determine_command,
    parse_download_link,
    parse_latest_version,
    parse_versions,
)


class TestURLBuilder:
    """Tests for URLBuilder dataclass."""

    def test_build_versions_url(self) -> None:
        """Test building versions URL."""
        builder = URLBuilder(name="youtube", package="com.google.android.youtube")
        expected = f"{APKPURE_BASE}/youtube/com.google.android.youtube/versions"
        assert builder.build_versions_url() == expected

    def test_build_download_url(self) -> None:
        """Test building download URL."""
        builder = URLBuilder(name="youtube", package="com.google.android.youtube")
        expected = f"{APKPURE_BASE}/youtube/com.google.android.youtube/download/19.16.39"
        assert builder.build_download_url("19.16.39") == expected

    def test_base_path_property(self) -> None:
        """Test base_path property."""
        builder = URLBuilder(name="app", package="com.example.app")
        assert builder.base_path == f"{APKPURE_BASE}/app/com.example.app"


class TestAppConfig:
    """Tests for AppConfig dataclass."""

    def test_basic_config(self) -> None:
        """Test creating basic config."""
        config = AppConfig(name="youtube", package="com.google.android.youtube")
        assert config.name == "youtube"
        assert config.package == "com.google.android.youtube"
        assert config.version is None

    def test_config_with_version(self) -> None:
        """Test creating config with version."""
        config = AppConfig(
            name="youtube",
            package="com.google.android.youtube",
            version="19.16.39",
        )
        assert config.version == "19.16.39"


class TestParseResult:
    """Tests for ParseResult dataclass."""

    def test_ok_factory(self) -> None:
        """Test ParseResult.ok factory method."""
        result = ParseResult.ok("19.16.39")
        assert result.success is True
        assert result.data == "19.16.39"
        assert result.error is None

    def test_err_factory(self) -> None:
        """Test ParseResult.err factory method."""
        result = ParseResult.err("not found")
        assert result.success is False
        assert result.data is None
        assert result.error == "not found"


class TestParseLatestVersion:
    """Tests for parse_latest_version function."""

    def test_extracts_from_ver_top_down(self) -> None:
        """Test extracting version from ver-top-down div."""
        html = '<div class="ver-top-down" data-dt-version="19.16.39"></div>'
        result = parse_latest_version(html)
        assert result.success is True
        assert result.data == "19.16.39"

    def test_extracts_from_ver_item(self) -> None:
        """Test extracting version from ver-item as fallback."""
        html = '<div class="ver-item"><a><span class="ver-item-n">19.16.39</span></a></div>'
        result = parse_latest_version(html)
        assert result.success is True
        assert result.data == "19.16.39"

    def test_returns_error_when_not_found(self) -> None:
        """Test returning error when version not found."""
        html = "<html><body>No version info</body></html>"
        result = parse_latest_version(html)
        assert result.success is False
        assert "not found" in result.error


class TestParseVersions:
    """Tests for parse_versions function."""

    def test_extracts_multiple_versions(self) -> None:
        """Test extracting multiple versions."""
        html = """
        <div class="ver-item"><a><span class="ver-item-n">19.16.39</span></a></div>
        <div class="ver-item"><a><span class="ver-item-n">19.15.36</span></a></div>
        <div class="ver-item"><a><span class="ver-item-n">19.14.35</span></a></div>
        """
        result = parse_versions(html)
        assert result.success is True
        assert result.data == ["19.16.39", "19.15.36", "19.14.35"]

    def test_deduplicates_versions(self) -> None:
        """Test that duplicate versions are deduplicated."""
        html = """
        <div class="ver-item"><a><span class="ver-item-n">19.16.39</span></a></div>
        <div class="ver-item"><a><span class="ver-item-n">19.16.39</span></a></div>
        """
        result = parse_versions(html)
        assert result.success is True
        assert result.data == ["19.16.39"]

    def test_returns_error_when_empty(self) -> None:
        """Test returning error when no versions found."""
        html = "<html><body>No versions</body></html>"
        result = parse_versions(html)
        assert result.success is False


class TestParseDownloadLink:
    """Tests for parse_download_link function."""

    def test_extracts_from_download_link_id(self) -> None:
        """Test extracting from a#download_link."""
        html = '<a id="download_link" href="https://download.example.com/app.apk">Download</a>'
        result = parse_download_link(html)
        assert result.success is True
        assert result.data == "https://download.example.com/app.apk"

    def test_extracts_from_da_class(self) -> None:
        """Test extracting from a.da as fallback."""
        html = '<a class="da" href="https://download.example.com/app.apk">Download</a>'
        result = parse_download_link(html)
        assert result.success is True
        assert result.data == "https://download.example.com/app.apk"

    def test_returns_error_when_not_found(self) -> None:
        """Test returning error when download link not found."""
        html = "<html><body>No download link</body></html>"
        result = parse_download_link(html)
        assert result.success is False


class TestDetermineCommand:
    """Tests for determine_command function."""

    def test_determines_latest(self) -> None:
        """Test determining LATEST command."""
        args = argparse.Namespace(
            latest=True,
            versions=False,
            download=False,
            url_only=False,
        )
        assert determine_command(args) == Command.LATEST

    def test_determines_versions(self) -> None:
        """Test determining VERSIONS command."""
        args = argparse.Namespace(
            latest=False,
            versions=True,
            download=False,
            url_only=False,
        )
        assert determine_command(args) == Command.VERSIONS

    def test_determines_download(self) -> None:
        """Test determining DOWNLOAD command."""
        args = argparse.Namespace(
            latest=False,
            versions=False,
            download=True,
            url_only=False,
        )
        assert determine_command(args) == Command.DOWNLOAD

    def test_url_only_takes_precedence(self) -> None:
        """Test that url_only takes precedence over other flags."""
        args = argparse.Namespace(
            latest=True,
            versions=False,
            download=False,
            url_only=True,
        )
        assert determine_command(args) == Command.URL_ONLY


@pytest.mark.parametrize(
    ("name", "package", "version"),
    [
        ("youtube", "com.google.android.youtube", None),
        ("youtube-music", "com.google.android.apps.youtube.music", "5.0.0"),
        ("reddit", "com.reddit.frontpage", "2024.10.0"),
    ],
)
def test_app_config_variations(name: str, package: str, version: str | None) -> None:
    """Test AppConfig creation with various inputs."""
    config = AppConfig(name=name, package=package, version=version)
    assert config.name == name
    assert config.package == package
    assert config.version == version
