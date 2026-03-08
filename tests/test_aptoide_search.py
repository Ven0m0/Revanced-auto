"""Test suite for Aptoide API client."""

from __future__ import annotations

import base64

import pytest

from scripts.aptoide_search import (
    APTOIDE_API,
    AptoideMetaResponse,
    AptoideResponse,
    Arch,
    DownloadInfo,
    QueryBuilder,
    find_vercode,
    is_valid_aptoide_response,
    is_valid_meta_response,
    parse_meta_download,
    parse_search_download,
    parse_search_version,
    parse_versions_list,
)


class TestArchEnum:
    """Tests for Arch enum."""

    def test_arch_values(self) -> None:
        """Test Arch enum values."""
        assert Arch.UNIVERSAL.value == "universal"
        assert Arch.ALL.value == "all"
        assert Arch.ARM64_V8A.value == "arm64-v8a"
        assert Arch.ARMEABI_V7A.value == "armeabi-v7a"

    def test_cpu_string_universal(self) -> None:
        """Test CPU string for universal arch."""
        assert Arch.UNIVERSAL.cpu_string == ""
        assert Arch.ALL.cpu_string == ""

    def test_cpu_string_arm64(self) -> None:
        """Test CPU string for arm64-v8a."""
        assert "arm64-v8a" in Arch.ARM64_V8A.cpu_string
        assert "armeabi-v7a" in Arch.ARM64_V8A.cpu_string


class TestQueryBuilder:
    """Tests for QueryBuilder dataclass."""

    def test_build_search_url_universal(self) -> None:
        """Test building search URL with universal arch."""
        builder = QueryBuilder(package="com.google.android.youtube", arch="universal")
        expected = f"{APTOIDE_API}/apps/search?query=com.google.android.youtube&limit=1&trusted=true"
        assert builder.build_search_url() == expected

    def test_build_search_url_with_arch(self) -> None:
        """Test building search URL with specific arch."""
        builder = QueryBuilder(package="com.google.android.youtube", arch="arm64-v8a")
        url = builder.build_search_url()
        assert url.startswith(f"{APTOIDE_API}/apps/search?")
        assert "q=" in url  # Should have encoded q param

    def test_build_versions_url(self) -> None:
        """Test building versions URL."""
        builder = QueryBuilder(
            package="com.google.android.youtube",
            arch="universal",
            limit=50,
        )
        expected = f"{APTOIDE_API}/listAppVersions?package_name=com.google.android.youtube&limit=50"
        assert builder.build_versions_url() == expected

    def test_build_meta_url(self) -> None:
        """Test building meta URL."""
        builder = QueryBuilder(package="com.google.android.youtube", arch="universal")
        url = builder.build_meta_url(vercode=12345)
        expected_base = f"{APTOIDE_API}/getAppMeta?package_name=com.google.android.youtube&vercode=12345"
        assert url.startswith(expected_base)


class TestDownloadInfo:
    """Tests for DownloadInfo dataclass."""

    def test_basic_info(self) -> None:
        """Test creating basic download info."""
        info = DownloadInfo(url="https://example.com/app.apk")
        assert info.url == "https://example.com/app.apk"
        assert info.vercode is None
        assert info.version is None

    def test_full_info(self) -> None:
        """Test creating download info with all fields."""
        info = DownloadInfo(
            url="https://example.com/app.apk",
            vercode=12345,
            version="19.16.39",
        )
        assert info.vercode == 12345
        assert info.version == "19.16.39"


class TestIsValidAptoideResponse:
    """Tests for is_valid_aptoide_response TypeGuard."""

    def test_valid_response(self) -> None:
        """Test valid AptoideResponse."""
        data: AptoideResponse = {
            "datalist": {
                "list": [
                    {"file": {"vername": "19.16.39", "vercode": 12345, "path": "url"}},
                ],
            },
        }
        assert is_valid_aptoide_response(data) is True

    def test_invalid_not_dict(self) -> None:
        """Test non-dict is invalid."""
        assert is_valid_aptoide_response("not a dict") is False
        assert is_valid_aptoide_response(None) is False
        assert is_valid_aptoide_response([1, 2, 3]) is False

    def test_invalid_no_datalist(self) -> None:
        """Test dict without datalist is invalid."""
        assert is_valid_aptoide_response({"other": "data"}) is False

    def test_invalid_datalist_not_dict(self) -> None:
        """Test dict with non-dict datalist is invalid."""
        assert is_valid_aptoide_response({"datalist": "not a dict"}) is False


class TestIsValidMetaResponse:
    """Tests for is_valid_meta_response TypeGuard."""

    def test_valid_response(self) -> None:
        """Test valid AptoideMetaResponse."""
        data: AptoideMetaResponse = {
            "data": {"file": {"vername": "19.16.39", "vercode": 12345, "path": "url"}},
        }
        assert is_valid_meta_response(data) is True

    def test_invalid_not_dict(self) -> None:
        """Test non-dict is invalid."""
        assert is_valid_meta_response("string") is False

    def test_invalid_no_data(self) -> None:
        """Test dict without data is invalid."""
        assert is_valid_meta_response({"other": "value"}) is False


class TestParseSearchVersion:
    """Tests for parse_search_version function."""

    def test_extracts_version(self) -> None:
        """Test extracting version from search response."""
        import orjson

        data: AptoideResponse = {
            "datalist": {
                "list": [{"file": {"vername": "19.16.39", "vercode": 12345}}],
            },
        }
        result = parse_search_version(orjson.dumps(data))
        assert result == "19.16.39"

    def test_returns_none_on_invalid_json(self) -> None:
        """Test returns None on invalid JSON."""
        result = parse_search_version("not valid json")
        assert result is None

    def test_returns_none_on_empty_list(self) -> None:
        """Test returns None when list is empty."""
        import orjson

        data: AptoideResponse = {"datalist": {"list": []}}
        result = parse_search_version(orjson.dumps(data))
        assert result is None


class TestParseSearchDownload:
    """Tests for parse_search_download function."""

    def test_extracts_download_url(self) -> None:
        """Test extracting download URL from search response."""
        import orjson

        data: AptoideResponse = {
            "datalist": {
                "list": [{"file": {"path": "https://example.com/app.apk", "vername": "1.0"}}],
            },
        }
        result = parse_search_download(orjson.dumps(data))
        assert result == "https://example.com/app.apk"

    def test_returns_none_when_no_path(self) -> None:
        """Test returns None when path not in response."""
        import orjson

        data: AptoideResponse = {
            "datalist": {"list": [{"file": {"vername": "1.0"}}]},
        }
        result = parse_search_download(orjson.dumps(data))
        assert result is None


class TestParseVersionsList:
    """Tests for parse_versions_list function."""

    def test_extracts_versions(self) -> None:
        """Test extracting versions list."""
        import orjson

        data: AptoideResponse = {
            "datalist": {
                "list": [
                    {"file": {"vername": "19.16.39"}},
                    {"file": {"vername": "19.15.36"}},
                    {"file": {"vername": "19.14.35"}},
                ],
            },
        }
        result = parse_versions_list(orjson.dumps(data))
        assert result == ["19.16.39", "19.15.36", "19.14.35"]

    def test_deduplicates_versions(self) -> None:
        """Test that duplicate versions are deduplicated."""
        import orjson

        data: AptoideResponse = {
            "datalist": {
                "list": [
                    {"file": {"vername": "19.16.39"}},
                    {"file": {"vername": "19.16.39"}},
                ],
            },
        }
        result = parse_versions_list(orjson.dumps(data))
        assert result == ["19.16.39"]

    def test_returns_empty_on_error(self) -> None:
        """Test returns empty list on error."""
        result = parse_versions_list("invalid json")
        assert result == []


class TestFindVercode:
    """Tests for find_vercode function."""

    def test_finds_vercode(self) -> None:
        """Test finding vercode for version."""
        import orjson

        data: AptoideResponse = {
            "datalist": {
                "list": [
                    {"file": {"vername": "19.16.39", "vercode": 12345}},
                    {"file": {"vername": "19.15.36", "vercode": 12344}},
                ],
            },
        }
        result = find_vercode(orjson.dumps(data), "19.15.36")
        assert result == 12344

    def test_returns_none_when_not_found(self) -> None:
        """Test returns None when version not found."""
        import orjson

        data: AptoideResponse = {
            "datalist": {"list": [{"file": {"vername": "19.16.39", "vercode": 12345}}]},
        }
        result = find_vercode(orjson.dumps(data), "19.15.36")
        assert result is None

    def test_returns_none_on_invalid_json(self) -> None:
        """Test returns None on invalid JSON."""
        result = find_vercode("invalid", "19.16.39")
        assert result is None


class TestParseMetaDownload:
    """Tests for parse_meta_download function."""

    def test_extracts_url(self) -> None:
        """Test extracting URL from meta response."""
        import orjson

        data: AptoideMetaResponse = {
            "data": {"file": {"path": "https://example.com/app.apk", "vername": "1.0"}},
        }
        result = parse_meta_download(orjson.dumps(data))
        assert result == "https://example.com/app.apk"

    def test_returns_none_when_no_path(self) -> None:
        """Test returns None when path not present."""
        import orjson

        data: AptoideMetaResponse = {"data": {"file": {"vername": "1.0"}}}
        result = parse_meta_download(orjson.dumps(data))
        assert result is None


class TestQueryBuilderQParam:
    """Tests for QueryBuilder q param generation."""

    def test_universal_returns_empty(self) -> None:
        """Test universal arch returns empty string."""
        builder = QueryBuilder(package="com.test.app", arch="universal")
        url = builder.build_search_url()
        assert "&q=" not in url

    def test_all_returns_empty(self) -> None:
        """Test all arch returns empty string."""
        builder = QueryBuilder(package="com.test.app", arch="all")
        url = builder.build_search_url()
        assert "&q=" not in url

    def test_arm64_returns_encoded(self) -> None:
        """Test arm64-v8a returns base64 encoded param."""
        builder = QueryBuilder(package="com.test.app", arch="arm64-v8a")
        url = builder.build_search_url()
        assert "&q=" in url
        # Extract and verify it's base64 encoded
        q_start = url.index("&q=") + 3
        encoded = url[q_start:]
        decoded = base64.b64decode(encoded).decode()
        assert "arm64-v8a" in decoded


@pytest.mark.parametrize(
    ("package", "arch", "limit"),
    [
        ("com.google.android.youtube", "universal", 50),
        ("com.google.android.apps.youtube.music", "arm64-v8a", 100),
        ("com.reddit.frontpage", "armeabi-v7a", 25),
    ],
)
def test_query_builder_variations(package: str, arch: str, limit: int) -> None:
    """Test QueryBuilder with various inputs."""
    builder = QueryBuilder(package=package, arch=arch, limit=limit)
    assert builder.package == package
    assert builder.arch == arch
    assert builder.limit == limit
