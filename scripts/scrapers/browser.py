"""Real-browser page fetch for pages behind a Cloudflare JS challenge."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from scripts.lib import logging as log

# APKMirror titles its challenge "Just a moment"; APKPure's interstitial is "Security Verification".
_CHALLENGE_TITLES = ("Just a moment", "Security Verification")
_BLOCKED_TITLE = "Attention Required"
# APKPure's interstitial took ~55 s to clear in a real browser.
_CHALLENGE_TIMEOUT_S = 180
# APKMirror's challenge usually clears in 10-25 s but sometimes spins forever until the page is reloaded.
_CHALLENGE_RELOAD_S = 60
# The release list renders just after the title flips, so reading at once can miss it.
_SETTLE_S = 2
_LAUNCH_TIMEOUT_S = 30
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
        self._process: Any = None

    async def _launch(self) -> Any:
        """Start Chrome ourselves, wait for its debug port, then let nodriver attach to it."""
        # Lazy so runs that never meet a challenge neither import nodriver nor need Chrome.
        import nodriver

        # GitHub's ubuntu-24.04 runners block Chrome's userns sandbox (AppArmor); nodriver only drops it for root.
        config = nodriver.Config(headless=False, sandbox=False)
        config.host = "127.0.0.1"
        config.port = nodriver.util.free_port()
        # nodriver itself waits only ~2.75 s for the debug port, too short for a cold headed Chrome on CI.
        self._process = await asyncio.create_subprocess_exec(
            str(config.browser_executable_path),
            *config(),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        for _ in range(_LAUNCH_TIMEOUT_S):
            if self._process.returncode is not None:
                msg = f"Chrome exited with code {self._process.returncode} before opening its debug port"
                raise RuntimeError(msg)
            try:
                _, writer = await asyncio.open_connection(config.host, config.port)
            except OSError:
                await asyncio.sleep(1)
                continue
            writer.close()
            return await nodriver.start(config)
        await self.aclose()
        msg = f"Chrome did not open its debug port within {_LAUNCH_TIMEOUT_S}s"
        raise RuntimeError(msg)

    async def _open(self, url: str) -> Any:
        """Open ``url`` in a tab and wait until any Cloudflare challenge has cleared."""
        if self._browser is None:
            self._browser = await self._launch()
        log.info(f"Cloudflare challenge, fetching via browser: {url}")
        tab = await self._browser.get(url)
        for second in range(1, _CHALLENGE_TIMEOUT_S + 1):
            await tab.sleep(1)
            if second % 10 == 0:  # TEMP-DEBUG
                import os

                os.makedirs("build", exist_ok=True)  # noqa: PTH103
                await tab.save_screenshot(f"build/cf-{second:03d}.png")
                with open(f"build/cf-{second:03d}.html", "w", encoding="utf-8") as f:  # noqa: PTH123, ASYNC230
                    f.write(await tab.get_content())
            if second % _CHALLENGE_RELOAD_S == 0:
                log.info(f"Cloudflare challenge stuck after {second}s, reloading: {url}")
                await tab.reload()
                continue
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
        if self._process is not None:  # nodriver does not own a Chrome it attached to
            with contextlib.suppress(ProcessLookupError):
                self._process.kill()
            await self._process.wait()
            self._process = None
