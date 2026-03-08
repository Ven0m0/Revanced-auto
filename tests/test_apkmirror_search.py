"""Test suite for APKMirror search parser."""

from __future__ import annotations

import pytest

from scripts.apkmirror_search import (
    ArchStrategy,
    RowData,
    SearchConfig,
    SearchResult,
    extract_download_url,
    get_target_archs,
    is_valid_row_node,
    parse_row_data,
    row_matches,
    search,
)


class TestArchStrategy:
    """Tests for ArchStrategy enum."""

    def test_arch_strategy_values(self) -> None:
        """Test ArchStrategy enum values."""
        assert ArchStrategy.ALL.value == "all"
        assert ArchStrategy.SPECIFIC.value == "specific"


class TestGetTargetArchs:
    """Tests for get_target_archs function."""

    def test_all_archs_returns_base_archs(self) -> None:
        """Test 'all' returns base architecture list."""
        result = get_target_archs("all")
        assert result == ["universal", "noarch", "arm64-v8a + armeabi-v7a"]

    def test_specific_arch_includes_fallbacks(self) -> None:
        """Test specific arch includes requested arch first then fallbacks."""
        result = get_target_archs("arm64-v8a")
        assert result[0] == "arm64-v8a"
        assert "universal" in result
        assert "noarch" in result
        assert "arm64-v8a + armeabi-v7a" in result

    def test_unknown_arch_still_has_fallbacks(self) -> None:
        """Test unknown arch still returns fallbacks."""
        result = get_target_archs("unknown-arch")
        assert result[0] == "unknown-arch"
        assert "universal" in result


class TestSearchConfig:
    """Tests for SearchConfig dataclass."""

    def test_config_creation(self) -> None:
        """Test creating SearchConfig."""
        config = SearchConfig(apk_bundle="APK", dpi="nodpi", arch="arm64-v8a")
        assert config.apk_bundle == "APK"
        assert config.dpi == "nodpi"
        assert config.arch == "arm64-v8a"


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_found_result(self) -> None:
        """Test successful search result."""
        result = SearchResult(
            found=True,
            url="https://www.apkmirror.com/apk/123",
            reason="found",
        )
        assert result.found is True
        assert result.url is not None

    def test_not_found_result(self) -> None:
        """Test unsuccessful search result."""
        result = SearchResult(
            found=False,
            url=None,
            reason="no_match_in_table",
        )
        assert result.found is False
        assert result.url is None


class TestRowData:
    """Tests for RowData dataclass."""

    def test_row_data_creation(self) -> None:
        """Test creating RowData."""
        row = RowData(
            version="19.16.39",
            size="120MB",
            bundle="APK",
            arch="arm64-v8a",
            android_ver="7.0+",
            dpi="nodpi",
        )
        assert row.version == "19.16.39"
        assert row.bundle == "APK"


class TestParseRowData:
    """Tests for parse_row_data function."""

    def test_valid_text_nodes(self) -> None:
        """Test parsing valid text nodes."""
        nodes = ["19.16.39", "120MB", "APK", "arm64-v8a", "7.0+", "nodpi"]
        result = parse_row_data(nodes)
        assert result is not None
        assert result.version == "19.16.39"
        assert result.bundle == "APK"
        assert result.arch == "arm64-v8a"

    def test_insufficient_fields_returns_none(self) -> None:
        """Test that insufficient fields returns None."""
        nodes = ["19.16.39", "120MB", "APK"]  # Only 3 fields
        result = parse_row_data(nodes)
        assert result is None

    def test_empty_list_returns_none(self) -> None:
        """Test that empty list returns None."""
        result = parse_row_data([])
        assert result is None


class TestRowMatches:
    """Tests for row_matches function."""

    def test_matching_row(self) -> None:
        """Test row that matches all criteria."""
        row_data = RowData(
            version="19.16.39",
            size="120MB",
            bundle="APK",
            arch="arm64-v8a",
            android_ver="7.0+",
            dpi="nodpi",
        )
        config = SearchConfig(apk_bundle="APK", dpi="nodpi", arch="arm64-v8a")
        target_archs = ["arm64-v8a", "universal"]

        assert row_matches(row_data, config, target_archs) is True

    def test_bundle_mismatch(self) -> None:
        """Test row with non-matching bundle."""
        row_data = RowData(
            version="19.16.39",
            size="120MB",
            bundle="BUNDLE",
            arch="arm64-v8a",
            android_ver="7.0+",
            dpi="nodpi",
        )
        config = SearchConfig(apk_bundle="APK", dpi="nodpi", arch="arm64-v8a")
        target_archs = ["arm64-v8a"]

        assert row_matches(row_data, config, target_archs) is False

    def test_arch_not_in_targets(self) -> None:
        """Test row with arch not in target list."""
        row_data = RowData(
            version="19.16.39",
            size="120MB",
            bundle="APK",
            arch="x86",
            android_ver="7.0+",
            dpi="nodpi",
        )
        config = SearchConfig(apk_bundle="APK", dpi="nodpi", arch="arm64-v8a")
        target_archs = ["arm64-v8a", "universal"]

        assert row_matches(row_data, config, target_archs) is False


class TestIsValidRowNode:
    """Tests for is_valid_row_node TypeGuard."""

    def test_valid_node_mock(self) -> None:
        """Test validation with mock node-like object."""
        # Can't easily test real Node without HTML, so test the negative cases
        assert is_valid_row_node(None) is False
        assert is_valid_row_node("string") is False
        assert is_valid_row_node(123) is False


class TestExtractDownloadUrl:
    """Tests for extract_download_url function."""

    def test_extracts_url_from_html(self) -> None:
        """Test URL extraction from valid HTML row."""
        html = '<div><a href="/apk/youtube/youtube-19-16-39-release/">Download</a></div>'
        from selectolax.parser import HTMLParser

        tree = HTMLParser(html)
        row = tree.css_first("div")
        result = extract_download_url(row)

        assert result == "https://www.apkmirror.com/apk/youtube/youtube-19-16-39-release/"

    def test_returns_none_no_link(self) -> None:
        """Test returns None when no link found."""
        html = "<div>No link here</div>"
        from selectolax.parser import HTMLParser

        tree = HTMLParser(html)
        row = tree.css_first("div")
        result = extract_download_url(row)

        assert result is None


class TestSearch:
    """Tests for search function."""

    def test_no_table_found(self) -> None:
        """Test search returns no_table_found when no rows exist."""
        html = "<html><body>No table here</body></html>"
        config = SearchConfig(apk_bundle="APK", dpi="nodpi", arch="arm64-v8a")
        result = search(html, config)

        assert result.found is False
        assert result.reason == "no_table_found"

    def test_table_but_no_match(self) -> None:
        """Test search returns no_match_in_table when no matching row."""
        html = """
        <div class="table-row headerFont">
            <div>19.16.39</div>
            <div>120MB</div>
            <div>BUNDLE</div>
            <div>arm64-v8a</div>
            <div>7.0+</div>
            <div>nodpi</div>
            <div><a href="/apk/123">Download</a></div>
        </div>
        """
        config = SearchConfig(apk_bundle="APK", dpi="nodpi", arch="arm64-v8a")
        result = search(html, config)

        assert result.found is False
        assert result.reason == "no_match_in_table"

    def test_successful_match(self) -> None:
        """Test search finds matching row."""
        html = """
        <div class="table-row headerFont">
            <div>19.16.39</div>
            <div>120MB</div>
            <div>APK</div>
            <div>arm64-v8a</div>
            <div>7.0+</div>
            <div>nodpi</div>
            <div><a href="/apk/youtube/19-16-39/">Download</a></div>
        </div>
        """
        config = SearchConfig(apk_bundle="APK", dpi="nodpi", arch="arm64-v8a")
        result = search(html, config)

        assert result.found is True
        assert result.url == "https://www.apkmirror.com/apk/youtube/19-16-39/"
        assert result.reason == "found"

    def test_fallback_arch_match(self) -> None:
        """Test search finds fallback arch when specific not available."""
        html = """
        <div class="table-row headerFont">
            <div>19.16.39</div>
            <div>120MB</div>
            <div>APK</div>
            <div>universal</div>
            <div>7.0+</div>
            <div>nodpi</div>
            <div><a href="/apk/youtube/universal/">Download</a></div>
        </div>
        """
        config = SearchConfig(apk_bundle="APK", dpi="nodpi", arch="arm64-v8a")
        result = search(html, config)

        assert result.found is True
        assert result.url == "https://www.apkmirror.com/apk/youtube/universal/"


@pytest.mark.parametrize(
    ("bundle", "dpi", "arch"),
    [
        ("APK", "nodpi", "arm64-v8a"),
        ("BUNDLE", "320dpi", "universal"),
        ("APK", "nodpi", "all"),
    ],
)
def test_search_config_variations(bundle: str, dpi: str, arch: str) -> None:
    """Test SearchConfig creation with various valid inputs."""
    config = SearchConfig(apk_bundle=bundle, dpi=dpi, arch=arch)
    assert config.apk_bundle == bundle
    assert config.dpi == dpi
    assert config.arch == arch
