"""Real-browser page fetch for pages behind a Cloudflare JS challenge."""

from __future__ import annotations

from typing import Any

from scripts.lib import logging as log

_CHALLENGE_TITLE = "Just a moment"
_BLOCKED_TITLE = "Attention Required"
_CHALLENGE_TIMEOUT_S = 30
# The release list renders just after the title flips, so reading at once can miss it.
_SETTLE_S = 2


class ChallengeBrowser:
    """Drives the installed Chrome via nodriver to read pages plain HTTP cannot.

    Runs headed: Cloudflare hard-blocks headless Chrome ("Attention Required"),
    so CI needs a virtual display (``xvfb-run``).
    """

    def __init__(self) -> None:
        self._browser: Any = None

    async def fetch_html(self, url: str) -> str:
        """Open ``url``, wait out the challenge and return the rendered HTML."""
        if self._browser is None:
            # Lazy so runs that never meet a challenge neither import nodriver nor need Chrome.
            import nodriver

            self._browser = await nodriver.start(headless=False)
        log.info(f"Cloudflare challenge, fetching via browser: {url}")
        tab = await self._browser.get(url)
        title = ""
        for _ in range(_CHALLENGE_TIMEOUT_S):
            await tab.sleep(1)
            title = await tab.evaluate("document.title") or ""
            if _BLOCKED_TITLE in title:
                msg = f"Cloudflare blocked the browser for {url}"
                raise RuntimeError(msg)
            if title and _CHALLENGE_TITLE not in title and not title.startswith("Loading"):
                await tab.sleep(_SETTLE_S)
                html: str = await tab.get_content()
                return html
        msg = f"Cloudflare challenge did not clear within {_CHALLENGE_TIMEOUT_S}s for {url}"
        raise RuntimeError(msg)

    async def aclose(self) -> None:
        """Stop the browser; safe to call repeatedly."""
        if self._browser is not None:
            self._browser.stop()
            self._browser = None
