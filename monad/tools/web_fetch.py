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

# Minimum meaningful content length (chars). Below this, page is likely
# a JS shell, Cloudflare challenge, or empty skeleton.
MIN_CONTENT_LEN = 200


def run(url: str = "", mode: str = "auto", selector: str = "",
        wait_selector: str = "", timeout: int = 30, **kwargs) -> str:
    """Fetch web page content with automatic mode selection.

    This is MONAD's internet perception capability (eyes).
    Use this to directly see what's on a web page.

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
    if mode not in ("auto", "fast", "stealth", "browser"):
        return f"Error: Invalid mode '{mode}'. Use 'auto', 'fast', 'stealth', or 'browser'."

    if mode == "auto":
        return _auto_fetch(url, selector, wait_selector, timeout)

    # Explicit mode — run exactly what user asked
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
    """Smart auto-fallback: fast → stealth → browser.

    Each mode is tried in order. If a mode fails or returns too little
    content (likely a JS shell / Cloudflare challenge), the next mode
    is attempted automatically.
    """
    errors = []

    # --- Stage 1: fast (HTTP) ---
    try:
        result = _fetch_fast(url, selector, timeout)
        if _is_good_content(result):
            return result
        errors.append(f"fast: content too short ({len(result.strip())} chars), likely JS-rendered page")
    except Exception as e:
        errors.append(f"fast: {_short_error(e)}")

    # --- Stage 2: stealth (anti-bot headless) ---
    try:
        result = _fetch_stealth(url, selector, timeout)
        if _is_good_content(result):
            return f"[mode: stealth]\n{result}"
        errors.append(f"stealth: content too short ({len(result.strip())} chars)")
    except Exception as e:
        errors.append(f"stealth: {_short_error(e)}")

    # --- Stage 3: browser (full Chromium + JS) ---
    try:
        result = _fetch_browser(url, selector, wait_selector, timeout)
        if _is_good_content(result):
            return f"[mode: browser]\n{result}"
        errors.append(f"browser: content too short ({len(result.strip())} chars)")
    except Exception as e:
        errors.append(f"browser: {_short_error(e)}")

    # All modes failed — if a selector was specified, retry without it
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
        # Fallback: requests + Scrapling parser (Adaptor)
        # Catches ImportError (curl_cffi missing) AND runtime errors
        # (e.g. curl_cffi TLS handshake failures)
        page = _requests_fetch(url, timeout)

    return _extract_content(page, selector)


def _fetch_stealth(url: str, selector: str, timeout: int) -> str:
    """Stealth fetch — headless browser with anti-bot bypass."""
    from scrapling.fetchers import StealthyFetcher

    page = StealthyFetcher.fetch(url, headless=True, timeout=timeout * 1000)
    return _extract_content(page, selector)


def _fetch_browser(url: str, selector: str, wait_selector: str, timeout: int) -> str:
    """Full browser rendering via system Chrome (no separate chromium install needed)."""
    from scrapling.fetchers import DynamicFetcher

    fetch_kwargs = {
        "headless": True,
        "real_chrome": True,
        "timeout": timeout * 1000,  # Playwright uses ms
        "network_idle": True,
    }

    page = DynamicFetcher.fetch(url, **fetch_kwargs)
    return _extract_content(page, selector)


def _requests_fetch(url: str, timeout: int):
    """Fallback: use requests + Scrapling Adaptor for parsing."""
    import requests
    from scrapling.parser import Adaptor

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
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

    # Return full page text, truncated to avoid overwhelming LLM
    try:
        text = page.get_all_text(ignore_tags=("script", "style", "noscript"))
    except (AttributeError, TypeError):
        text = ""

    if not text or not text.strip():
        try:
            text = page.body.text if page.body else ""
        except (AttributeError, TypeError):
            # Last resort: get raw text
            text = page.text if hasattr(page, "text") else ""

    return _truncate(text, 5000)


def _is_good_content(text: str) -> bool:
    """Check if extracted content is meaningful (not a JS shell or challenge page)."""
    clean = text.strip()
    if not clean or len(clean) < MIN_CONTENT_LEN:
        return False
    # Detect common challenge / empty page patterns
    challenge_markers = [
        "please solve the challenge",
        "checking your browser",
        "just a moment",
        "enable javascript",
        "you need to enable javascript",
    ]
    lower = clean.lower()
    for marker in challenge_markers:
        if marker in lower and len(clean) < 500:
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


def _truncate(text: str, max_len: int = 5000) -> str:
    """Truncate text to max_len with notice."""
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
    msg = str(e)
    if len(msg) > 120:
        msg = msg[:120] + "..."
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
