"""
MONAD Tool: Web Fetch
MONAD's perception capability — see the internet directly.

Four modes:
  - auto:    Smart auto-fallback: fast → stealth → browser (DEFAULT)
  - fast:    HTTP request with smart parsing (requests + Scrapling parser)
  - stealth: Headless browser with anti-bot bypass (Scrapling StealthyFetcher)
  - browser: Full browser with JS rendering, uses system Chrome (Scrapling DynamicFetcher)
"""

import traceback

from monad.config import (
    MIN_CONTENT_LEN, CHALLENGE_CONTENT_THRESHOLD,
    CHALLENGE_MARKERS, DEFAULT_USER_AGENT, TRUNCATE_CONTENT, truncate,
)

_VALID_MODES = ("auto", "fast", "stealth", "browser")


def run(url: str = "", mode: str = "auto", selector: str = "",
        wait_selector: str = "", timeout: int = 30, **kwargs) -> str:
    """Fetch web page content with automatic mode selection.

    This is MONAD's internet perception capability (eyes).

    Args:
        url: Target URL to fetch
        mode: "auto" (smart fallback, default), "fast", "stealth", "browser"
        selector: CSS selector to extract specific elements (optional)
        wait_selector: Wait for this element before extracting (browser mode only)
        timeout: Request timeout in seconds (default: 30)

    Returns:
        Page text content, or extracted element text if selector is provided
    """
    if not url:
        return "Error: No URL provided."

    mode = mode.lower().strip()
    if mode not in _VALID_MODES:
        return f"Error: Invalid mode '{mode}'. Use: {', '.join(_VALID_MODES)}."

    if mode == "auto":
        return _auto_fetch(url, selector, wait_selector, timeout)

    try:
        if mode == "fast":
            return _fetch_fast(url, selector, timeout)
        elif mode == "stealth":
            return _fetch_stealth(url, selector, timeout)
        elif mode == "browser":
            return _fetch_browser(url, selector, wait_selector, timeout)
    except ImportError as e:
        return _import_error_msg(mode, e)
    except Exception:
        error = traceback.format_exc()
        return f"[web_fetch error in '{mode}' mode]\n{error}"


def _auto_fetch(url: str, selector: str, wait_selector: str, timeout: int) -> str:
    """Smart auto-fallback: fast → stealth → browser."""
    errors = []

    for mode_name, fetcher in (
        ("fast", lambda: _fetch_fast(url, selector, timeout)),
        ("stealth", lambda: _fetch_stealth(url, selector, timeout)),
        ("browser", lambda: _fetch_browser(url, selector, wait_selector, timeout)),
    ):
        try:
            result = fetcher()
            if _is_good_content(result):
                prefix = f"[mode: {mode_name}]\n" if mode_name != "fast" else ""
                return f"{prefix}{result}"
            errors.append(f"{mode_name}: content too short ({len(result.strip())} chars)")
        except Exception as e:
            errors.append(f"{mode_name}: {_short_error(e)}")

    if selector:
        retry_result = _auto_fetch(url, "", wait_selector, timeout)
        if _is_good_content(retry_result):
            return f"[selector '{selector}' matched nothing, fetched full page instead]\n{retry_result}"

    fallback = "\n".join(f"  - {e}" for e in errors)
    return (
        f"[web_fetch] All modes failed for {url}:\n{fallback}\n\n"
        f"Suggestion: Try python_exec with requests/BeautifulSoup, "
        f"or check if the URL is correct."
    )


def _fetch_fast(url: str, selector: str, timeout: int) -> str:
    """Fast HTTP fetch. Uses Scrapling Fetcher if available, falls back to requests."""
    try:
        from scrapling.fetchers import Fetcher
        page = Fetcher.get(url, stealthy_headers=True, timeout=timeout)
    except Exception:
        page = _requests_fetch(url, timeout)

    return _extract_content(page, selector)


def _fetch_stealth(url: str, selector: str, timeout: int) -> str:
    """Stealth fetch — headless browser with anti-bot bypass."""
    from scrapling.fetchers import StealthyFetcher
    page = StealthyFetcher.fetch(url, headless=True, timeout=timeout * 1000)
    return _extract_content(page, selector)


def _fetch_browser(url: str, selector: str, wait_selector: str, timeout: int) -> str:
    """Full browser rendering via system Chrome."""
    from scrapling.fetchers import DynamicFetcher
    page = DynamicFetcher.fetch(
        url, headless=True, real_chrome=True,
        timeout=timeout * 1000, network_idle=True,
    )
    return _extract_content(page, selector)


def _requests_fetch(url: str, timeout: int):
    """Fallback: use requests + Scrapling Adaptor for parsing."""
    import requests
    from scrapling.parser import Adaptor

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }

    resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    resp.encoding = resp.apparent_encoding or resp.encoding
    resp.raise_for_status()

    return Adaptor(resp.text, url=url)


def _extract_content(page, selector: str) -> str:
    """Extract content from a Scrapling page/adaptor object."""
    if selector:
        elements = page.css(selector)
        if not elements:
            return f"No elements found matching selector: {selector}\n\nPage title: {_safe_title(page)}"
        texts = [el.text.strip() for el in elements if el.text and el.text.strip()]
        return "\n".join(texts) if texts else "(elements found but no text content)"

    try:
        text = page.get_all_text(ignore_tags=("script", "style", "noscript"))
    except (AttributeError, TypeError):
        text = ""

    if not text or not text.strip():
        try:
            text = page.body.text if page.body else ""
        except (AttributeError, TypeError):
            text = page.text if hasattr(page, "text") else ""

    return _truncate_page(text)


def _is_good_content(text: str) -> bool:
    """Check if extracted content is meaningful (not a JS shell or challenge page)."""
    clean = text.strip()
    if not clean or len(clean) < MIN_CONTENT_LEN:
        return False
    lower = clean.lower()
    for marker in CHALLENGE_MARKERS:
        if marker in lower and len(clean) < CHALLENGE_CONTENT_THRESHOLD:
            return False
    return True


def _safe_title(page) -> str:
    """Safely extract page title."""
    try:
        title = page.css("title")
        if title:
            return title[0].text.strip()
    except Exception:
        pass
    return "(unknown)"


def _truncate_page(text: str, max_len: int = TRUNCATE_CONTENT) -> str:
    """Truncate page text with notice."""
    text = text.strip()
    if not text:
        return "(page loaded but no text content extracted)"
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n\n... [truncated, {len(text) - max_len} chars omitted]"


def _import_error_msg(mode: str, e: Exception) -> str:
    """Generate helpful error message for missing dependencies."""
    hints = {
        "stealth": "pip install 'scrapling[stealth]' (requires camoufox)",
        "browser": "pip install playwright (requires Chrome browser installed on system)",
    }
    hint = hints.get(mode, "pip install requests")
    return f"Error: Missing dependency for '{mode}' mode.\nInstall: {hint}\nDetail: {e}"


def _short_error(e: Exception) -> str:
    """Get a concise error description."""
    msg = truncate(str(e), 120)
    return f"{type(e).__name__}: {msg}"


TOOL_META = {
    "name": "web_fetch",
    "description": (
        "Fetch and extract web page content. "
        "MONAD's internet perception capability (eyes). "
        "Modes: auto (smart fallback, default), fast (HTTP), stealth (anti-bot), browser (JS render)."
    ),
    "inputs": ["url", "mode", "selector", "wait_selector", "timeout"],
}
