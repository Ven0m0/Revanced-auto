"""Test suite for APKMonk scraper.

Smoke tests for APKMonkScraper class focusing on instantiation,
pure methods, and utility functions without network access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from scripts.scrapers.apkmonk import APKMonkScraper
from scripts.scrapers.base import DownloadSource, VersionInfo


class TestAPKMonkScraperInstantiation:
    """Tests for APKMonkScraper instantiation."""

    def test_scraper_instantiation(self) -> None:
        """Test that APKMonkScraper can be instantiated."""
        scraper = APKMonkScraper()
        assert scraper is not None
        assert scraper.source == DownloadSource.APKMonk

    def test_scraper_session_creation(self) -> None:
        """Test that scraper creates an HTTP session."""
        scraper = APKMonkScraper()
        session = scraper.session
        assert session is not None
        scraper.close()

    def test_scraper_close(self) -> None:
        """Test that scraper can be closed."""
        scraper = APKMonkScraper()
        session = scraper.session
        assert session is not None
        scraper.close()
        # After close, session should be None
        assert scraper._session is None


class TestAPKMonkScraperPackageName:
    """Tests for APKMonkScraper.get_package_name method."""

    def test_extract_package_name_from_valid_url(self) -> None:
        """Test extracting package name from valid APKMonk URL."""
        scraper = APKMonkScraper()
        url = "https://www.apkmonk.com/app/com.google.android.youtube/"
        package = scraper.get_package_name(url)
        assert package == "com.google.android.youtube"
        scraper.close()

    def test_extract_package_name_without_trailing_slash(self) -> None:
        """Test extracting package name from URL without trailing slash."""
        scraper = APKMonkScraper()
        url = "https://www.apkmonk.com/app/com.spotify.music"
        package = scraper.get_package_name(url)
        assert package == "com.spotify.music"
        scraper.close()

    def test_extract_package_name_with_download_path(self) -> None:
        """Test extracting package name from download URL."""
        scraper = APKMonkScraper()
        url = "https://www.apkmonk.com/app/com.android.chrome/download/1.0.0"
        package = scraper.get_package_name(url)
        assert package == "com.android.chrome"
        scraper.close()

    def test_extract_package_name_invalid_url_returns_none(self) -> None:
        """Test that invalid URL returns None."""
        scraper = APKMonkScraper()
        url = "https://www.google.com"
        package = scraper.get_package_name(url)
        assert package is None
        scraper.close()

    def test_extract_package_name_malformed_url_returns_none(self) -> None:
        """Test that malformed URL returns None."""
        scraper = APKMonkScraper()
        url = "not a url"
        package = scraper.get_package_name(url)
        assert package is None
        scraper.close()


class TestAPKMonkScraperBuildUrl:
    """Tests for APKMonkScraper._build_url method."""

    def test_build_base_url(self) -> None:
        """Test building base app URL."""
        scraper = APKMonkScraper()
        url = scraper._build_url("com.example.app")
        assert url == "https://www.apkmonk.com/app/com.example.app"
        scraper.close()

    def test_build_url_with_path(self) -> None:
        """Test building URL with path suffix."""
        scraper = APKMonkScraper()
        url = scraper._build_url("com.example.app", "download/1.0.0")
        assert url == "https://www.apkmonk.com/app/com.example.app/download/1.0.0"
        scraper.close()

    def test_build_url_with_empty_path(self) -> None:
        """Test building URL with empty path."""
        scraper = APKMonkScraper()
        url = scraper._build_url("com.example.app", "")
        assert url == "https://www.apkmonk.com/app/com.example.app"
        scraper.close()


class TestAPKMonkScraperParseVersions:
    """Tests for APKMonkScraper._parse_versions_page method."""

    def test_parse_versions_with_no_versions(self) -> None:
        """Test parsing HTML with no versions."""
        scraper = APKMonkScraper()
        html = "<html><body></body></html>"
        versions = scraper._parse_versions_page(html)
        assert isinstance(versions, list)
        assert len(versions) == 0
        scraper.close()

    def test_parse_versions_with_version_content_divs(self) -> None:
        """Test parsing HTML with version-content divs."""
        scraper = APKMonkScraper()
        html = """
        <div class="version-content">
            <span class="version">1.0.0</span>
            <a class="download-btn" href="https://example.com/download">Download</a>
        </div>
        """
        versions = scraper._parse_versions_page(html)
        assert len(versions) == 1
        assert versions[0].version == "1.0.0"
        assert versions[0].url == "https://example.com/download"
        scraper.close()

    def test_parse_versions_with_related_ver_content_divs(self) -> None:
        """Test parsing HTML with related-ver-content divs."""
        scraper = APKMonkScraper()
        html = """
        <div class="related-ver-content">
            <span class="version">2.0.0</span>
            <a class="download-btn" href="https://example.com/download2">Download</a>
        </div>
        """
        versions = scraper._parse_versions_page(html)
        assert len(versions) == 1
        assert versions[0].version == "2.0.0"
        assert versions[0].url == "https://example.com/download2"
        scraper.close()

    def test_parse_versions_mixed_content(self) -> None:
        """Test parsing HTML with mixed version types."""
        scraper = APKMonkScraper()
        html = """
        <div class="version-content">
            <span class="version">1.0.0</span>
            <a class="download-btn" href="https://example.com/1">Download</a>
        </div>
        <div class="related-ver-content">
            <span class="version">2.0.0</span>
            <a class="download-btn" href="https://example.com/2">Download</a>
        </div>
        """
        versions = scraper._parse_versions_page(html)
        assert len(versions) == 2
        assert versions[0].version == "1.0.0"
        assert versions[1].version == "2.0.0"
        scraper.close()

    def test_parse_versions_missing_url(self) -> None:
        """Test parsing version without download URL."""
        scraper = APKMonkScraper()
        html = """
        <div class="version-content">
            <span class="version">1.0.0</span>
        </div>
        """
        versions = scraper._parse_versions_page(html)
        assert len(versions) == 1
        assert versions[0].version == "1.0.0"
        assert versions[0].url is None
        scraper.close()


class TestAPKMonkScraperParseDownloadLink:
    """Tests for APKMonkScraper._parse_download_link method."""

    def test_parse_download_link_from_anchor(self) -> None:
        """Test parsing download link from anchor tag."""
        scraper = APKMonkScraper()
        html = '<a class="download-link" href="https://example.com/apk.apk">Download</a>'
        url = scraper._parse_download_link(html)
        assert url == "https://example.com/apk.apk"
        scraper.close()

    def test_parse_download_link_from_div_button(self) -> None:
        """Test parsing download link from div button."""
        scraper = APKMonkScraper()
        html = '<div class="download-btn"><a href="https://example.com/apk2.apk">Download</a></div>'
        url = scraper._parse_download_link(html)
        assert url == "https://example.com/apk2.apk"
        scraper.close()

    def test_parse_download_link_not_found(self) -> None:
        """Test parsing when no download link exists."""
        scraper = APKMonkScraper()
        html = "<html><body><p>No download here</p></body></html>"
        url = scraper._parse_download_link(html)
        assert url is None
        scraper.close()

    def test_parse_download_link_with_whitespace(self) -> None:
        """Test parsing download link with surrounding whitespace."""
        scraper = APKMonkScraper()
        html = '<a class="download-link" href="  https://example.com/apk.apk  ">Download</a>'
        url = scraper._parse_download_link(html)
        assert url == "https://example.com/apk.apk"
        scraper.close()

    def test_parse_download_link_prefers_anchor_over_div(self) -> None:
        """Test that anchor.download-link is preferred over div.download-btn."""
        scraper = APKMonkScraper()
        html = """
        <a class="download-link" href="https://example.com/anchor.apk">Anchor</a>
        <div class="download-btn"><a href="https://example.com/div.apk">Div</a></div>
        """
        url = scraper._parse_download_link(html)
        assert url == "https://example.com/anchor.apk"
        scraper.close()


class TestVersionInfoDataclass:
    """Tests for VersionInfo dataclass."""

    def test_version_info_creation(self) -> None:
        """Test creating VersionInfo."""
        info = VersionInfo(version="1.0.0", url="https://example.com/apk.apk")
        assert info.version == "1.0.0"
        assert info.url == "https://example.com/apk.apk"
        assert info.arch is None
        assert info.dpi is None

    def test_version_info_with_optional_fields(self) -> None:
        """Test creating VersionInfo with optional fields."""
        info = VersionInfo(
            version="2.0.0",
            url="https://example.com/apk.apk",
            arch="arm64",
            dpi="xxhdpi",
        )
        assert info.version == "2.0.0"
        assert info.arch == "arm64"
        assert info.dpi == "xxhdpi"
