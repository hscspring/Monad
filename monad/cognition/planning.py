"""
Plan parsing and plan-vs-action alignment for the Reasoner.

Keeps decomposition JSON extraction and semantic capability matching testable
and separate from the main loop.
"""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_array(raw: str) -> str | None:
    """Return the first top-level JSON array substring using bracket matching.

    Handles nested brackets and strings (with basic escape support), unlike
    naive find('[') + rfind(']').
    """
    start = raw.find("[")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    quote: str | None = None
    for i in range(start, len(raw)):
        c = raw[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif quote and c == quote:
                in_string = False
                quote = None
            continue
        if c in "\"'":
            in_string = True
            quote = c
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]
    return None


def parse_plan_steps(raw: str) -> list[dict[str, Any]]:
    """Parse LLM plan output into step dicts. Returns [] on failure."""
    text = raw.strip()
    if "```" in text:
        text = re.sub(r"```\w*\n?", "", text).strip()
    fragment = extract_json_array(text)
    if fragment is None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        steps = data if isinstance(data, list) else []
    else:
        try:
            steps = json.loads(fragment)
        except json.JSONDecodeError:
            return []
    if not isinstance(steps, list) or not steps:
        return []
    out: list[dict[str, Any]] = []
    for s in steps:
        if isinstance(s, dict) and s.get("step"):
            out.append(
                {
                    "step": s.get("step", ""),
                    "capability": s.get("capability", ""),
                    "done": False,
                }
            )
    return out


BASIC_CAPABILITIES = frozenset(
    {"python_exec", "shell", "web_fetch", "ask_user", "desktop_control"}
)


def code_suggests_http_fetch(code: str) -> bool:
    """Heuristic: python_exec code likely fetched remote HTTP content."""
    if not code:
        return False
    c = code.lower()
    client_hints = (
        "requests.",
        "urllib",
        "httpx",
        "aiohttp",
        "web_fetch(",
        "http.client",
    )
    if not any(h in c for h in client_hints):
        return False
    context_hints = (
        "http://",
        "https://",
        "url",
        ".get(",
        ".post(",
        "request(",
    )
    return any(h in c for h in context_hints)


def action_satisfies_planned_capability(
    planned: str,
    actual: str,
    params: dict[str, Any],
    known_skills: frozenset[str],
) -> bool:
    """Whether an executed action satisfies a planned step capability.

    Treats some capability substitutions as equivalent (e.g. python_exec + HTTP
    client as a stand-in for web_fetch).
    """
    planned = (planned or "").strip()
    actual = (actual or "").strip()
    if not planned or not actual:
        return False
    if actual == planned:
        return True
    code = (params.get("code") or "") if isinstance(params.get("code"), str) else ""
    cmd = (params.get("command") or "") if isinstance(params.get("command"), str) else ""
    cmd_lower = cmd.lower()

    if planned == "web_fetch":
        if actual == "web_fetch":
            return True
        if actual == "python_exec" and code_suggests_http_fetch(code):
            return True
        if actual == "shell" and any(x in cmd_lower for x in ("curl", "wget", "http")):
            return True

    if planned == "shell":
        if actual == "shell":
            return True
        if actual == "python_exec" and any(
            x in code for x in ("subprocess", "os.system", "os.popen")
        ):
            return True

    if planned == "python_exec" and actual == "python_exec":
        return True

    if planned == "ask_user" and actual == "ask_user":
        return True
    if planned == "desktop_control" and actual == "desktop_control":
        return True

    # Named skill: explicit call or inline reference in code
    if planned in known_skills or planned not in BASIC_CAPABILITIES:
        if actual == planned:
            return True
        if actual == "python_exec" and planned and planned in code:
            return True

    return False
