"""Invisible (headless) Chrome used only for research: web search and reading pages.

Everything the user sees opens in their own Chrome profile instead (chrome_profiles.py).
Playwright's sync API is bound to the thread that started it; all tool calls come from the
voice-pipeline thread. Started on first use.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

log = logging.getLogger("jarvis.browser")

# Some sites refuse the default "HeadlessChrome" user agent.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"


class BrowserError(Exception):
    """A browser action failed; the message is safe to show and speak."""


class BrowserSession:
    def __init__(self, profile_dir: Path) -> None:
        self._profile_dir = profile_dir
        self._playwright = None
        self._context = None
        self._thread: int | None = None

    def page(self) -> Page:
        if self._thread is not None and self._thread != threading.get_ident():
            raise BrowserError("Browser used from the wrong thread")
        if self._context is not None:
            try:
                return self._context.pages[-1] if self._context.pages else self._context.new_page()
            except PlaywrightError:
                log.info("Research browser went away; restarting it")
                self._shutdown()
        self._start()
        return self._context.pages[0] if self._context.pages else self._context.new_page()

    def close(self) -> None:
        self._shutdown()

    def _retrying(self, work):
        """Run `work(page)`, and if the browser died mid-operation, restart it and try once more.

        `page()` already replaces a context that is gone, but a headless browser can also be
        killed part-way through a navigation, which surfaced as "Target page, context or browser
        has been closed" in the middle of a search.
        """
        try:
            return work(self.page())
        except PlaywrightError as exc:
            if "closed" not in str(exc).lower():
                raise
            log.info("Research browser died mid-request; restarting and retrying once")
            self._shutdown()
            return work(self.page())

    def web_search(self, query: str) -> dict:
        return self._retrying(lambda page: self._web_search(page, query))

    def _web_search(self, page: Page, query: str) -> dict:
        # DuckDuckGo's HTML page: Google shows captchas to automated browsers.
        page.goto(f"https://html.duckduckgo.com/html/?q={quote_plus(query)}", wait_until="domcontentloaded", timeout=30_000)
        results = page.evaluate("""() => [...document.querySelectorAll('.result')].slice(0, 6).map(r => ({
            title: r.querySelector('.result__a')?.textContent.trim() || '',
            url: r.querySelector('.result__a')?.href || '',
            snippet: r.querySelector('.result__snippet')?.textContent.trim() || ''}))""")
        for result in results:
            result["url"] = _unwrap_redirect(result["url"])
        if not results:
            raise BrowserError(f"The search for {query!r} returned no results.")
        return {"query": query, "results": results}

    def read(self, url: str, limit: int = 4000) -> dict:
        return self._retrying(lambda page: self._read(page, url, limit))

    def _read(self, page: Page, url: str, limit: int = 4000) -> dict:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(1.0)  # let script-rendered content appear
        text = " ".join(page.evaluate("() => document.body ? document.body.innerText : ''").split())
        return {"url": page.url, "title": page.title(), "text": text[:limit], "truncated": len(text) > limit}

    def _start(self) -> None:
        started = time.perf_counter()
        self._profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        try:
            self._context = self._playwright.chromium.launch_persistent_context(
                str(self._profile_dir),
                channel="chrome",  # the installed Google Chrome, not a downloaded browser
                headless=True,
                user_agent=USER_AGENT,
            )
        except PlaywrightError as exc:
            self._shutdown()
            raise BrowserError(f"Couldn't start Chrome: {str(exc).splitlines()[0]}") from exc
        self._thread = threading.get_ident()
        log.info("Research browser started in %.1f s", time.perf_counter() - started)

    def _shutdown(self) -> None:
        for closer in (lambda: self._context and self._context.close(), lambda: self._playwright and self._playwright.stop()):
            try:
                closer()
            except Exception:
                log.debug("Ignoring error while closing browser", exc_info=True)
        self._context = self._playwright = self._thread = None


def _unwrap_redirect(url: str) -> str:
    target = parse_qs(urlparse(url).query).get("uddg")
    return target[0] if target else url
