from __future__ import annotations

import json
import logging
import os
import re

import httpx

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5"


def llm_available() -> bool:
    key = os.environ.get("ANTHROPIC_API_KEY")
    return bool(key and key.strip())


def batch_categorize_descriptions(
    items: list[tuple[int, str]],
    allowed_categories: list[str],
) -> dict[int, str]:
    """Classify transaction descriptions via Anthropic API. Descriptions only — never PDFs."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not items:
        return {}

    payload_lines = [{"id": i, "description": desc[:500]} for i, desc in items]
    categories_str = ", ".join(allowed_categories)
    user_content = (
        "Assign each transaction description exactly one category from this list:\n"
        f"{categories_str}\n\n"
        "Return ONLY valid JSON: an array of objects with keys id (number) and category (string).\n\n"
        f"Transactions:\n{json.dumps(payload_lines)}"
    )

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": HAIKU_MODEL,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": user_content}],
                },
            )
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPError:
        logger.exception("LLM categorization request failed")
        return {}

    text_blocks = [
        b.get("text", "")
        for b in body.get("content", [])
        if b.get("type") == "text"
    ]
    raw = "\n".join(text_blocks).strip()
    return _parse_llm_json(raw, allowed_categories, {i for i, _ in items})


def _parse_llm_json(
    raw: str,
    allowed: list[str],
    valid_ids: set[int],
) -> dict[int, str]:
    allowed_set = set(allowed)
    match = re.search(r"\[[\s\S]*\]", raw)
    if not match:
        return {}
    try:
        arr = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    out: dict[int, str] = {}
    for entry in arr:
        if not isinstance(entry, dict):
            continue
        tid = entry.get("id")
        cat = entry.get("category")
        if not isinstance(tid, int) or tid not in valid_ids:
            continue
        if isinstance(cat, str) and cat in allowed_set and cat != "Unknown":
            out[tid] = cat
    return out
