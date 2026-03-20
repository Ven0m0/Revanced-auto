
from scripts.apkmonk_search import parse_version_url, parse_versions


def test_parse_versions() -> None:
    """Test parse_versions with valid HTML."""
    html = """
    <div class="striped">
        <a href="/v1">1.0.0</a>
        <a href="/v2">2.0.0</a>
    </div>
    <div class="striped">
        <a href="/v3">3.0.0</a>
    </div>
    """
    result = parse_versions(html)
    assert result.success is True
    assert result.data == ["1.0.0", "2.0.0", "3.0.0"]


def test_parse_versions_no_versions() -> None:
    """Test parse_versions with no versions in HTML."""
    html = "<div>No versions here</div>"
    result = parse_versions(html)
    assert result.success is False
    assert result.error is not None
    assert "no versions found" in result.error.lower()


def test_parse_version_url_found() -> None:
    """Test parse_version_url with a found version."""
    html = """
    <div class="striped">
        <a href="/v1">1.0.0</a>
        <a href="/v2">2.0.0</a>
    </div>
    """
    result = parse_version_url(html, "2.0.0")
    assert result.success is True
    assert result.data == "https://www.apkmonk.com/v2"


def test_parse_version_url_not_found() -> None:
    """Test parse_version_url with a version not found."""
    html = """
    <div class="striped">
        <a href="/v1">1.0.0</a>
    </div>
    """
    result = parse_version_url(html, "2.0.0")
    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error.lower()


def test_parse_versions_duplicates() -> None:
    """Test parse_versions with duplicate versions in HTML."""
    html = """
    <div class="striped">
        <a href="/v1">1.0.0</a>
        <a href="/v1-alt">1.0.0</a>
    </div>
    """
    result = parse_versions(html)
    assert result.success is True
    assert result.data == ["1.0.0"]
