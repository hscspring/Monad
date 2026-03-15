"""
Skill: publish_to_xhs
Publish image+text notes to Xiaohongshu (小红书) via Playwright browser automation.

Uses a persistent browser profile at ~/.monad/browser/xhs_profile/ —
login once, and the session persists across runs (just like a real Chrome profile).

Optionally generates a knowledge map via doc2mermaid and attaches it as
an extra image alongside the text-card slides.

Usage:
  login()               # first-time: opens browser, you log in, close when done
  run(title="...", ...)  # publish using saved session
"""

import os
import time
import tempfile
from pathlib import Path

BROWSER_DIR = Path(os.path.expanduser("~/.monad/browser"))
PROFILE_DIR = BROWSER_DIR / "xhs_profile"
PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?source=official&from=tab_switch&target=image"


def _get_context(playwright, headless=False):
    """Launch a persistent browser context that remembers login state."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        return playwright.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=headless, channel="chrome",
            args=["--disable-blink-features=AutomationControlled"])
    except Exception:
        return playwright.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=headless,
            args=["--disable-blink-features=AutomationControlled"])


def login(**kwargs):
    """Open browser for XHS login. Close the browser when you're done.

    Uses a persistent profile — just like a real Chrome window.
    Log in however you want (QR code, phone, password). When you're
    done and see the homepage feed, simply close the browser window.
    The session is saved automatically.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = _get_context(p, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.xiaohongshu.com/")

        print("=" * 50)
        print("浏览器已打开，请完成小红书登录")
        print("登录成功后，直接关闭浏览器窗口即可")
        print("会话会自动保存，下次无需重新登录")
        print("=" * 50)

        # Wait until the browser is closed by the user
        try:
            page.wait_for_event("close", timeout=300_000)
        except Exception:
            pass

        try:
            context.close()
        except Exception:
            pass

    return "✅ 浏览器已关闭，登录状态已自动保存"


def _ensure_node_path():
    """Prepend a modern Node.js (>=18) to PATH so mmdc works."""
    nvm_dir = os.path.expanduser("~/.nvm/versions/node")
    if not os.path.isdir(nvm_dir):
        return
    for ver in sorted(os.listdir(nvm_dir), reverse=True):
        bin_dir = os.path.join(nvm_dir, ver, "bin")
        mmdc_path = os.path.join(bin_dir, "mmdc")
        if os.path.isfile(mmdc_path):
            major = ver.lstrip("v").split(".")[0]
            if int(major) >= 18:
                current = os.environ.get("PATH", "")
                if bin_dir not in current:
                    os.environ["PATH"] = f"{bin_dir}:{current}"
                return


def _generate_knowledge_map(content):
    """Generate a knowledge map PNG from text via doc2mermaid.

    Returns the path to the generated PNG, or None on failure.
    """
    try:
        from doc2mermaid.core import doc_to_map
    except ImportError:
        return None

    llm_base_url = os.getenv("MONAD_BASE_URL", "")
    llm_api_key = os.getenv("MONAD_API_KEY", "")
    llm_model = os.getenv("MODEL_ID", "")
    if not all([llm_base_url, llm_api_key, llm_model]):
        return None

    _ensure_node_path()

    out_path = os.path.join(tempfile.gettempdir(), "xhs_knowledge_map.png")
    try:
        result = doc_to_map(
            content, output=out_path,
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
        )
        if result and os.path.isfile(result):
            return result
    except Exception:
        pass
    return None


def _add_extra_images(page, image_paths):
    """Add extra images on the final publish page via the hidden file input."""
    valid = [p for p in image_paths if os.path.isfile(p)]
    if not valid:
        return
    file_input = page.locator('.img-upload-area input[type="file"]').first
    try:
        file_input.set_input_files(valid)
    except Exception:
        file_input = page.locator('input[accept*=".png"]').first
        file_input.set_input_files(valid)
    time.sleep(2 + len(valid))


def _upload_images_flow(page, images):
    """Upload user-provided images. Returns True if images were uploaded."""
    valid_images = [f for f in images if os.path.isfile(f)]
    if not valid_images:
        return False
    file_input = page.locator('input[type="file"]').first
    file_input.set_input_files(valid_images)
    time.sleep(2 + len(valid_images))
    return True


_CARD_SUMMARY_PROMPT = """你是小红书文案专家。将以下内容精炼为3-5句话的文字卡片文案。

要求：
- 总共只写3-5句话，极度精炼
- 每句话不超过15个字
- 第一句是主题，后面是最核心的2-4个要点
- 去掉所有符号(•-等)，不要编号
- 用原文语言
- 只返回文案本身，不要其他内容

原文：
"""


def _summarize_for_card(content):
    """Use LLM to condense content into 3-5 short sentences for XHS text cards."""
    try:
        from openai import OpenAI
    except ImportError:
        return _fallback_flatten(content)

    base_url = os.getenv("MONAD_BASE_URL", "")
    api_key = os.getenv("MONAD_API_KEY", "")
    model = os.getenv("MODEL_ID", "")
    if not all([base_url, api_key, model]):
        return _fallback_flatten(content)

    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _CARD_SUMMARY_PROMPT + content}],
            temperature=0.3,
            max_tokens=200,
        )
        text = resp.choices[0].message.content.strip()
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if 2 <= len(lines) <= 8:
            return "\n".join(lines[:5])
    except Exception:
        pass
    return _fallback_flatten(content)


def _fallback_flatten(text):
    """Simple fallback: take first 5 non-empty lines, remove bullet markers."""
    import re
    text = text.replace("\r\n", "\n")
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"^\s*[•·\-–—]\s*", "", line).strip()
        if line:
            lines.append(line[:20])
        if len(lines) >= 5:
            break
    return "\n".join(lines)


def _text_card_flow(page, content):
    """Generate image cards from text (文字配图 mode).

    Flow: 文字配图 → fill text → 生成图片 → 下一步 → final publish page.
    """
    page.get_by_text("文字配图").click()
    time.sleep(3)

    card_text = _summarize_for_card(content)
    editor = page.locator(".ProseMirror").first
    editor.click()
    time.sleep(0.3)
    editor.fill(card_text)
    time.sleep(1)

    page.get_by_text("生成图片").click()
    page.wait_for_selector("text=下一步", timeout=15000)
    time.sleep(2)

    page.get_by_text("下一步").click()
    page.wait_for_selector('[placeholder*="填写标题"]', timeout=10000)
    time.sleep(2)


def _fill_and_publish(page, title, content, topics, has_images=False):
    """Fill title, content, topics, then click publish."""
    title_input = page.locator('[placeholder*="填写标题"]').first
    title_input.click()
    title_input.fill(title[:20])
    time.sleep(0.5)

    editor = page.locator(".ProseMirror").first
    editor.click()
    time.sleep(0.3)
    page.keyboard.press("Meta+A")
    page.keyboard.press("Backspace")
    time.sleep(0.3)
    page.keyboard.type(content, delay=5)
    time.sleep(0.5)

    page.keyboard.press("Enter")
    page.keyboard.press("Enter")
    time.sleep(0.3)

    for topic in topics[:5]:
        page.keyboard.type(f"#{topic}", delay=60)
        time.sleep(1.5)
        try:
            first_item = page.locator(".items .item").first
            if first_item.is_visible(timeout=3000):
                first_item.click()
                time.sleep(0.5)
        except Exception:
            pass
        page.keyboard.type(" ", delay=30)
        time.sleep(0.3)

    publish_btn = page.locator("button").filter(has_text="发布").last
    publish_btn.scroll_into_view_if_needed()
    publish_btn.click()
    time.sleep(3)


def run(title="", content="", topics=None, images=None, **kwargs):
    """Publish a note to Xiaohongshu.

    Two modes:
    - With images: uploads images, then fills title + content + topics.
    - Without images: uses "文字配图" to generate image cards from text,
      then fills title + topics on the final publish page.

    When knowledge_map is True (default), generates a knowledge map via
    doc2mermaid and attaches it as an extra slide.

    Args:
        title:          Note title (truncated to 20 chars for XHS limit)
        content:        Note body text
        topics:         List of topic/hashtag strings (e.g. ["AI", "技术分享"])
        images:         List of image file paths to upload
        knowledge_map:  If True, auto-generate a knowledge map image (default True)
        source_url:     Original article URL, appended to content body
    """
    if not title:
        return "Error: title 不能为空"
    if not content:
        return "Error: content 不能为空"
    if not PROFILE_DIR.exists():
        return "Error: 未找到浏览器 profile，请先运行 login() 登录小红书"

    from playwright.sync_api import sync_playwright

    topics = topics or []
    images = images or []
    knowledge_map = kwargs.get("knowledge_map", True)
    source_url = kwargs.get("source_url", "")

    if source_url:
        content = f"{content}\n\n原文链接：{source_url}"

    kmap_path = None
    if knowledge_map:
        kmap_path = _generate_knowledge_map(content)

    with sync_playwright() as p:
        context = _get_context(p, headless=False)
        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto(PUBLISH_URL)
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            url = page.url.lower()
            if "login" in url or "passport" in url:
                context.close()
                return "Error: 登录态已过期，请重新运行 login()"

            has_images = False
            if images:
                has_images = _upload_images_flow(page, images)

            if not has_images:
                _text_card_flow(page, content)

            if kmap_path:
                _add_extra_images(page, [kmap_path])

            _fill_and_publish(page, title, content, topics, has_images=has_images)

            parts = [f"✅ 已发布到小红书: 《{title[:20]}》"]
            if kmap_path:
                parts.append(f"📊 已附加知识图谱: {kmap_path}")
            result = "\n".join(parts)

        except Exception as e:
            result = f"❌ 发布失败: {str(e)}"
        finally:
            try:
                context.close()
            except Exception:
                pass

    return result
