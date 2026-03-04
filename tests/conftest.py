"""Shared pytest fixtures and utilities."""

from __future__ import annotations

# Add project root to path for imports
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return PROJECT_ROOT / "tests" / "fixtures"


@pytest.fixture
def sample_html_basic() -> str:
    """Return basic HTML fixture for parser tests."""
    return """
    <html>
        <body>
            <div class="content">
                <p>Paragraph 1</p>
                <p class="special">Paragraph 2</p>
            </div>
            <a href="https://example.com" class="link">Link 1</a>
            <a href="https://test.com" class="link" id="link2">Link 2</a>
            <div id="empty"></div>
            <div class="nested">
                <span>Nested Text</span>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def sample_uptodown_html() -> str:
    """Return sample Uptodown HTML content."""
    return (
        '<p>arm64-v8a</p><div class="v-report" data-file-id="12345"></div>'
        '<p>x86</p><div class="v-report" data-file-id="11111"></div>'
    )


@pytest.fixture
def sample_apkmirror_html() -> str:
    """Return sample APKMirror HTML content."""
    return """
    <div class="table-row headerFont">
        <div>19.16.39</div>
        <div>120MB</div>
        <div>APK</div>
        <div>arm64-v8a</div>
        <div>7.0+</div>
        <div>nodpi</div>
        <div><a href="/apk/youtube/youtube-19-16-39-release/">Download</a></div>
    </div>
    <div class="table-row headerFont">
        <div>19.16.39</div>
        <div>120MB</div>
        <div>APK</div>
        <div>universal</div>
        <div>7.0+</div>
        <div>nodpi</div>
        <div><a href="/apk/youtube/youtube-19-16-39-universal-release/">Download</a></div>
    </div>
    """


@pytest.fixture
def sample_toml_content() -> str:
    """Return sample TOML content for testing."""
    return """
[app]
name = "TestApp"
version = "1.0.0"

[build]
cli-version = "5.0.0"
patches-version = "4.0.0"
"""


@pytest.fixture
def sample_json_content() -> str:
    """Return sample JSON content for testing."""
    return '{"name": "TestApp", "version": "1.0.0"}'


@pytest.fixture
def temp_state_file(tmp_path: Path) -> Path:
    """Return path to a temporary state file."""
    return tmp_path / "test_state.json"


@pytest.fixture
def temp_toml_file(tmp_path: Path, sample_toml_content: str) -> Path:
    """Return path to a temporary TOML file with sample content."""
    path = tmp_path / "test_config.toml"
    path.write_text(sample_toml_content)
    return path


@pytest.fixture
def temp_json_file(tmp_path: Path, sample_json_content: str) -> Path:
    """Return path to a temporary JSON file with sample content."""
    path = tmp_path / "test_config.json"
    path.write_text(sample_json_content)
    return path


class MockHTMLParser:
    """Mock HTML parser for testing."""

    def __init__(self, html_content: str) -> None:
        self.html_content = html_content
        self.body = MockNode(html_content)

    def css(self, selector: str) -> list[MockNode]:
        """Return empty list by default - override for specific tests."""
        return []

    def css_first(self, selector: str) -> MockNode | None:
        """Return None by default - override for specific tests."""
        return None


class MockNode:
    """Mock node for HTML parsing tests."""

    def __init__(self, text_content: str = "", attrs: dict[str, str] | None = None) -> None:
        self._text = text_content
        self.attrs = attrs or {}
        self.child = MockChild(text_content)
        self.next: MockNode | None = None

    def text(self, *, strip: bool = False, deep: bool = False) -> str:  # noqa: ARG002
        """Return text content, optionally stripped."""
        result = self._text
        if strip:
            result = result.strip()
        return result

    def css(self, selector: str) -> list[MockNode]:  # noqa: ARG002
        """Return empty list by default."""
        return []

    def css_first(self, selector: str) -> MockNode | None:  # noqa: ARG002
        """Return None by default."""
        return None


class MockChild:
    """Mock child node."""

    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


@pytest.fixture
def mock_html_parser() -> type[MockHTMLParser]:
    """Return MockHTMLParser class."""
    return MockHTMLParser
