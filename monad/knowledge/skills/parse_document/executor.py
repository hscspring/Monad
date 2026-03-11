def run(**kwargs):
    """Parse a document into Markdown using docling.

    Supports PDF, DOCX, PPTX, XLSX, HTML, images (PNG/JPEG/TIFF),
    LaTeX, and more. Requires: pip install docling

    Args (via kwargs):
        file_path: Path to the document file (required).

    Returns:
        Markdown text of the document content.
    """
    file_path = kwargs.get("file_path")
    if not file_path:
        return "Error: file_path is required"

    import os
    if not os.path.exists(file_path):
        return f"Error: file not found: {file_path}"

    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(file_path)
        markdown = result.document.export_to_markdown()

        if not markdown or not markdown.strip():
            return f"Warning: document parsed but produced empty content ({file_path})"

        return markdown

    except ImportError:
        return "Error: docling is not installed. Run: pip install docling"
    except Exception as e:
        return f"Error parsing document: {type(e).__name__}: {e}"
