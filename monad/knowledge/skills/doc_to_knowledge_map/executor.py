def run(**kwargs):
    """Convert document/article/URL to a visual knowledge map (SVG/PNG).

    Accepts three input modes (priority: text > url > file_path):
      - text:      Raw document text
      - url:       Web page URL (auto-fetched via web_fetch)
      - file_path: Local file path (auto-read)

    Requires: pip install doc2mermaid
    Also needs: npm install -g @mermaid-js/mermaid-cli

    Args (via kwargs):
        text:        Document text (optional if url or file_path provided).
        url:         Web page URL to fetch (optional).
        file_path:   Local file to read (optional).
        output_path: Output file path (.svg or .png).
                     Default: ~/.monad/output/knowledge_map.svg

    Returns:
        Absolute path to the generated image file, or error message.
    """
    import os

    text = kwargs.get("text", "")
    url = kwargs.get("url", "")
    file_path = kwargs.get("file_path", "")

    if not text and url:
        try:
            html = web_fetch(url=url)
            if not html or len(html.strip()) < 50:
                return f"Error: web_fetch returned insufficient content for {url}"
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                body = soup.find("article") or soup.find("main") or soup.body
                text = body.get_text("\n", strip=True) if body else html
            except ImportError:
                text = html
        except Exception as e:
            return f"Error fetching URL: {e}"

    if not text and file_path:
        file_path = os.path.expanduser(file_path)
        if not os.path.exists(file_path):
            return f"Error: file not found: {file_path}"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            return f"Error reading file: {e}"

    if not text or not text.strip():
        return "Error: no input provided. Pass text, url, or file_path."

    default_output = os.path.expanduser("~/.monad/output/knowledge_map.svg")
    output_path = kwargs.get("output_path", default_output)

    try:
        from doc2mermaid.core import doc_to_map
    except ImportError:
        return "Error: doc2mermaid is not installed. Run: pip install doc2mermaid"

    llm_base_url = kwargs.get("llm_base_url", "") or os.getenv("MONAD_BASE_URL", "")
    llm_api_key = kwargs.get("llm_api_key", "") or os.getenv("MONAD_API_KEY", "")
    llm_model = kwargs.get("llm_model", "") or os.getenv("MODEL_ID", "")

    if not all([llm_base_url, llm_api_key, llm_model]):
        return "Error: LLM config required. Pass llm_base_url/llm_api_key/llm_model or set MONAD env vars."

    try:
        result = doc_to_map(
            text,
            output=output_path,
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
        )
        return f"Knowledge map saved to: {result}"
    except Exception as e:
        return f"Error generating knowledge map: {type(e).__name__}: {e}"
