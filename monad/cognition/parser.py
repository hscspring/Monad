"""
MONAD Cognition: Response Parser
Parses LLM JSON responses with robust error handling.
"""

import json
import re

from monad.config import TRUNCATE_MEDIUM, TRUNCATE_LONG
from monad.interface.output import Output


def parse_response(raw: str) -> dict:
    """Parse LLM response into structured format.

    Handles:
    - Pure JSON
    - JSON wrapped in markdown code blocks
    - JSON mixed with text labels (e.g. '思考: {...}')
    - Multiple JSON objects (takes the first valid one)
    - Truncated JSON (attempts to fix)
    - <think>...</think> XML blocks (stripped)
    - Alternative format: {"action": ..., "params": ...}
    """
    cleaned = clean_llm_output(raw)

    # Strategy 1: Direct parse
    try:
        parsed = json.loads(cleaned)
        normalized = _normalize_parsed(parsed)
        if normalized:
            return normalized
    except json.JSONDecodeError:
        pass

    # Strategy 2: Find JSON object in mixed text
    result = _extract_json_object(cleaned)
    if result:
        return result

    # Strategy 3: Fix truncated JSON
    result = _fix_truncated_json(cleaned)
    if result:
        return result

    # Strategy 4: Handle [TOOL_CALL] format (model leakage)
    result = _parse_tool_call_format(cleaned)
    if result:
        return result

    # Strategy 5: Treat plain text as thought
    if len(cleaned) > 10 and '{' not in cleaned:
        return {"type": "thought", "content": cleaned[:TRUNCATE_LONG]}

    return {"type": "error", "content": f"JSON 解析失败: {raw[:TRUNCATE_MEDIUM]}"}


def parse_tags(text: str) -> list[str]:
    """Extract tags from a reflection summary or experience block.

    Recognizes lines starting with 'Tags:', '5. Tags:', '5.' etc.
    Returns lowercase tag strings with '#' stripped.
    """
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("tags:") or lower.startswith("5. tags:") or lower.startswith("5."):
            raw = stripped.split(":", 1)[-1] if ":" in stripped else stripped
            tags = []
            for token in raw.replace("#", " ").replace("，", " ").replace(",", " ").split():
                token = token.strip().lower()
                if len(token) >= 2:
                    tags.append(token)
            return tags
    return []


def clean_llm_output(raw: str) -> str:
    """Strip think-tag blocks, XML tags, and markdown fences from LLM output."""
    cleaned = raw.strip()
    cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL).strip()
    cleaned = re.sub(r'<think>.*$', '', cleaned, flags=re.DOTALL).strip()
    cleaned = re.sub(
        r'</?(?:think|minimax:tool_call|invoke|parameter)[^>]*>',
        '',
        cleaned,
    ).strip()

    if "```" in cleaned:
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    return cleaned


def _normalize_parsed(parsed: dict) -> dict | None:
    """Normalize alternative JSON formats into the standard format."""
    if "type" in parsed:
        ptype = parsed["type"]
        if ptype == "ask_user":
            question = parsed.get("content", "") or parsed.get("question", "")
            return {
                "type": "action",
                "capability": "ask_user",
                "params": {"question": question},
            }
        return parsed

    if "action" in parsed:
        return {
            "type": "action",
            "capability": parsed["action"],
            "params": parsed.get("params", {}),
        }
    if "capability" in parsed:
        return {
            "type": "action",
            "capability": parsed["capability"],
            "params": parsed.get("params", {}),
        }
    if "answer" in parsed:
        return {"type": "answer", "content": parsed["answer"]}
    if "thought" in parsed:
        return {"type": "thought", "content": parsed["thought"]}
    return None


def _extract_json_object(text: str) -> dict | None:
    """Find the first valid JSON object in mixed text."""
    brace_depth = 0
    json_start = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if brace_depth == 0:
                json_start = i
            brace_depth += 1
        elif ch == '}':
            brace_depth -= 1
            if brace_depth == 0 and json_start >= 0:
                candidate = text[json_start:i + 1]
                try:
                    parsed = json.loads(candidate)
                    normalized = _normalize_parsed(parsed)
                    if normalized:
                        return normalized
                except json.JSONDecodeError:
                    pass
                json_start = -1
    return None


def _fix_truncated_json(text: str) -> dict | None:
    """Attempt to repair truncated JSON by adding closing braces."""
    start = text.find("{")
    if start < 0:
        return None

    fragment = text[start:]
    if '"type"' not in fragment:
        return None

    for fix in ['}", "}"}', '"}', '}', '"]}', '"}}']:
        try:
            parsed = json.loads(fragment + fix)
            if "type" in parsed:
                Output.warn("JSON 被截断，已自动修复")
                return parsed
        except json.JSONDecodeError:
            continue
    return None


def _parse_tool_call_format(text: str) -> dict | None:
    """Handle [TOOL_CALL] format from Minimax model leakage."""
    tool_call_match = re.search(r'\[TOOL_CALL\].*?tool\s*=>\s*"(\w+)"', text)
    if not tool_call_match:
        return None

    tool_name = tool_call_match.group(1)
    arg_match = re.search(r'--question\s+"([^"]*)', text)
    arg_val = arg_match.group(1) if arg_match else ""

    if tool_name == "ask_user":
        return {"type": "action", "capability": "ask_user",
                "params": {"question": arg_val}}
    return {"type": "action", "capability": tool_name, "params": {}}
