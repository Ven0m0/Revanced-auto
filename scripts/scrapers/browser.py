"""Real-browser page fetch for pages behind a Cloudflare JS challenge."""

from __future__ import annotations

import contextlib
from typing import Any

from scripts.lib import logging as log

# APKMirror titles its challenge "Just a moment"; APKPure's interstitial is "Security Verification".
_CHALLENGE_TITLES = ("Just a moment", "Security Verification")
_BLOCKED_TITLE = "Attention Required"
# APKPure's interstitial took ~55 s to clear in a real browser.
_CHALLENGE_TIMEOUT_S = 90
# The release list renders just after the title flips, so reading at once can miss it.
_SETTLE_S = 2
_DOWNLOAD_ATTEMPTS = 3
_DOWNLOAD_WAIT_S = 20
_DOWNLOAD_SETTLE_S = 4
# A cookie banner can overlay the page and swallow clicks (Uptodown).
_CONSENT_REJECT = "Reject all"
# The banner is injected by a late-loading script, so it can show well after the page title is set.
_CONSENT_WAIT_S = 10
# Records where a page would send the browser to download a file, instead of letting Chrome save it.
_CAPTURE_DOWNLOAD_JS = """
window.__href = null;
HTMLAnchorElement.prototype.click = function () { window.__href = this.href; };
"""


class ChallengeBrowser:
    """Drives the installed Chrome via nodriver to read pages plain HTTP cannot.

    Runs headed: Cloudflare hard-blocks headless Chrome ("Attention Required"),
    so CI needs a virtual display (``xvfb-run``).
    """

    def __init__(self) -> None:
        self._browser: Any = None

    async def _open(self, url: str) -> Any:
        """Open ``url`` in a tab and wait until any Cloudflare challenge has cleared."""
        if self._browser is None:
            # Lazy so runs that never meet a challenge neither import nodriver nor need Chrome.
            import nodriver

            # GitHub's ubuntu-24.04 runners block Chrome's userns sandbox (AppArmor); nodriver only drops it for root.
            self._browser = await nodriver.start(headless=False, sandbox=False)
        log.info(f"Cloudflare challenge, fetching via browser: {url}")
        tab = await self._browser.get(url)
        for _ in range(_CHALLENGE_TIMEOUT_S):
            await tab.sleep(1)
            title = str(await tab.evaluate("document.title") or "")
            if _BLOCKED_TITLE in title:
                msg = f"Cloudflare blocked the browser for {url}"
                raise RuntimeError(msg)
            if title and not any(t in title for t in _CHALLENGE_TITLES) and not title.startswith("Loading"):
                await tab.sleep(_SETTLE_S)
                return tab
        msg = f"Cloudflare challenge did not clear within {_CHALLENGE_TIMEOUT_S}s for {url}"
        raise RuntimeError(msg)

    async def fetch_html(self, url: str) -> str:
        """Open ``url``, wait out the challenge and return the rendered HTML."""
        tab = await self._open(url)
        html: str = await tab.get_content()
        return html

    async def capture_download_url(self, url: str, button: str) -> str:
        """Open ``url``, click the ``button`` CSS selector and return the URL the page tries to download.

        For downloads gated by a Cloudflare Turnstile token, which only a real browser can obtain.
        The file itself is not downloaded by the browser; the caller fetches the returned URL.
        """
        # The Turnstile token is sometimes never issued and re-clicking does not help, but a fresh page load does.
        for _ in range(_DOWNLOAD_ATTEMPTS):
            tab = await self._open(url)
            with contextlib.suppress(Exception):  # no banner on this page, or already dismissed
                reject = await tab.find(_CONSENT_REJECT, best_match=True, timeout=_CONSENT_WAIT_S)
                await reject.click()
            # The download handler only reacts once the page's scripts settle after the banner; an earlier click is lost.
            await tab.sleep(_DOWNLOAD_SETTLE_S)
            await tab.evaluate(_CAPTURE_DOWNLOAD_JS)
            await (await tab.select(button)).click()
            for _ in range(_DOWNLOAD_WAIT_S):
                await tab.sleep(1)
                href = await tab.evaluate("window.__href")
                if href:
                    return str(href)
        msg = f"No download URL from {url} after {_DOWNLOAD_ATTEMPTS} attempts"
        raise RuntimeError(msg)

    async def aclose(self) -> None:
        """Stop the browser; safe to call repeatedly."""
        if self._browser is not None:
            self._browser.stop()
            self._browser = None
