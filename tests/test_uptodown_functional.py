import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.scrapers.uptodown import UptodownScraper
from scripts.scrapers.base import DownloadResult

@pytest.fixture
def scraper():
    return UptodownScraper()

@pytest.mark.asyncio
async def test_download_success(scraper, tmp_path):
    pkg_name = "youtube"
    version = "19.01.33"
    output_path = tmp_path / "youtube.apk"

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.content = b"fake apk content"
    mock_response.status_code = 200

    # Mock get_versions to avoid network calls during test
    with (
        patch.object(scraper, "get_versions") as mock_get_versions,
        patch.object(scraper, "_find_version_by_file_id") as mock_find_version,
        patch.object(scraper.session, "get", return_value=mock_response)
    ):
        from scripts.scrapers.base import VersionInfo
        from scripts.scrapers.uptodown import UptodownVersion

        mock_get_versions.return_value = [
            VersionInfo(version=version, url="https://youtube.en.uptodown.com/android/download/123")
        ]
        mock_find_version.return_value = [
            UptodownVersion(version=version, url="https://youtube.en.uptodown.com/android/download/123", arch=None, file_id="123")
        ]

        result = await scraper.download(pkg_name, version, output_path)

        assert result.success is True
        assert result.file_path == output_path
        assert output_path.read_bytes() == b"fake apk content"

@pytest.mark.asyncio
async def test_fetch_page_success(scraper):
    url = "https://example.com"
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.text = "<html><body>Test</body></html>"
    mock_response.status_code = 200

    with patch.object(scraper.session, "get", return_value=mock_response):
        html = await scraper._fetch_page(url)
        assert html == "<html><body>Test</body></html>"

@pytest.mark.asyncio
async def test_fetch_page_failure(scraper):
    url = "https://example.com"

    with patch.object(scraper.session, "get", side_effect=httpx.HTTPError("Network error")):
        # We need to mock time.sleep because _request_with_retry uses it
        with patch("time.sleep"):
            html = await scraper._fetch_page(url)
            assert html is None
