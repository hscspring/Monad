import re
from html import unescape


def run(**kwargs):
    """Fetch a web page and convert it to Markdown.

    Uses MONAD's web_fetch (injected at runtime) to retrieve content,
    then parses HTML → Markdown with BeautifulSoup.

    Args (via kwargs):
        url: The web page URL (required).

    Returns:
        Markdown string of the page content.
    """
    url = kwargs.get("url")
    if not url:
        return "Error: url is required"

    html = web_fetch(url=url)
    if not html or len(html.strip()) < 50:
        return f"Error: web_fetch returned insufficient content for {url}"

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "Error: beautifulsoup4 is not installed. Run: pip install beautifulsoup4"

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    title_tag = (
        soup.find("h1", id="activity-name")
        or soup.find("h1", class_="title")
        or soup.find("h1")
        or soup.find("title")
    )
    title = title_tag.get_text(strip=True) if title_tag else ""

    content_div = (
        soup.find("div", id="js_content")
        or soup.find("div", class_="rich_media_content")
        or soup.find("article")
        or soup.find("main")
        or soup.body
    )
    if not content_div:
        return "Error: could not locate main content on the page"

    parts = []
    if title:
        parts.append(f"# {title}\n")

    for el in content_div.find_all(
        ["p", "h1", "h2", "h3", "h4", "h5", "h6",
         "ul", "ol", "blockquote", "pre", "img"]
    ):
        if el.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(el.name[1])
            text = el.get_text(strip=True)
            if text:
                parts.append(f"{'#' * level} {text}\n")

        elif el.name == "p":
            imgs = el.find_all("img")
            for img in imgs:
                src = img.get("data-src") or img.get("src")
                if src:
                    parts.append(f"![image]({src})\n")
            text = el.get_text(strip=True)
            if text:
                parts.append(text + "\n")

        elif el.name == "ul":
            for li in el.find_all("li", recursive=False):
                parts.append(f"- {li.get_text(strip=True)}")
            parts.append("")

        elif el.name == "ol":
            for i, li in enumerate(el.find_all("li", recursive=False), 1):
                parts.append(f"{i}. {li.get_text(strip=True)}")
            parts.append("")

        elif el.name == "blockquote":
            text = el.get_text(strip=True)
            if text:
                parts.append(f"> {text}\n")

        elif el.name == "pre":
            code = el.get_text()
            parts.append(f"```\n{code}\n```\n")

        elif el.name == "img":
            src = el.get("data-src") or el.get("src")
            if src:
                parts.append(f"![image]({src})\n")

    md = "\n".join(parts)
    md = unescape(md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()
