"""
Rule manager — calls an LLM (Groq or OpenAI) to translate a natural-language
rule request into a structured JSON dict that can be merged into the engine.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a chess rule-generator for a game called "Chaos Chess".
Your job is to translate a user's natural-language request into a JSON object
that modifies the game rules.

The JSON MUST contain ONLY keys from the following allowed set and valid values:

{
  "allow_castling": true | false,
  "allow_en_passant": true | false,
  "allow_promotion": true | false,
  "promotion_piece": "queen" | "rook" | "bishop" | "knight",
  "pawn_double_move": true | false,
  "capture_only": true | false,
  "inverse_colors": true | false,
  "extra_description": "<short human-readable summary of ALL active non-default rules>"
}

Rules:
1. Return ONLY valid JSON — no markdown fences, no prose, no comments.
2. Include ONLY the keys you are changing PLUS "extra_description".
3. "extra_description" must summarise the COMPLETE set of non-default rules
   (merge with the current rules provided by the user).
4. Be creative but keep the game playable.
"""


# ---------------------------------------------------------------------------
# Lazy client factory
# ---------------------------------------------------------------------------

def _make_client():
    """Create an AsyncOpenAI client lazily, only when needed."""
    from openai import AsyncOpenAI

    groq_key = os.getenv("GROQ_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")

    if groq_key:
        return AsyncOpenAI(
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1/",
        ), "llama3-8b-8192"

    elif openai_key:
        return AsyncOpenAI(api_key=openai_key), os.getenv("LLM_MODEL", "gpt-4o-mini")
    else:
        return None, None


# ---------------------------------------------------------------------------
# Public async function
# ---------------------------------------------------------------------------

async def update_rules_with_llm(
    current_rules: dict,
    user_request: str,
) -> dict:
    """
    Ask the LLM to produce new rule overrides based on *user_request*.

    Returns a dict that can be passed directly to `engine.update_rules()`.
    Raises `ValueError` if the LLM response cannot be parsed as valid JSON.
    """
    client, model = _make_client()
    if client is None:
        raise ValueError("No LLM API key configured. Falling back to simple parser.")

    rules_summary = json.dumps(current_rules, ensure_ascii=False, indent=2)
    user_message = (
        f"Current rules:\n{rules_summary}\n\n"
        f"User request: {user_request}\n\n"
        "Return only the JSON with the rule changes."
    )

    logger.info("Sending rule-change request to LLM (model=%s): %s", model, user_request)

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_tokens=512,
    )

    raw = response.choices[0].message.content or ""
    logger.debug("LLM raw response: %s", raw)

    # Strip optional markdown code fences
    cleaned = re.sub(r"```[a-z]*\n?", "", raw).strip()

    try:
        new_rules: dict = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned invalid JSON.\nRaw response:\n{raw}"
        ) from exc

    return new_rules


# ---------------------------------------------------------------------------
# Fallback: simple keyword-based rule parsing (no LLM key required)
# ---------------------------------------------------------------------------

def update_rules_simple(current_rules: dict, user_request: str) -> dict:
    """
    Lightweight keyword parser used as a fallback when no LLM key is set.
    Returns a partial rule dict.
    """
    req = user_request.lower()
    changes: dict = {}

    if any(w in req for w in ["no castle", "без рокировки", "castling off", "запрети рокировку", "запрет рокировки"]):
        changes["allow_castling"] = False
    if any(w in req for w in ["castle on", "рокировку разреши", "castling on"]):
        changes["allow_castling"] = True

    if any(w in req for w in ["no en passant", "без взятия на проходе", "запрети взятие на проходе"]):
        changes["allow_en_passant"] = False
    if any(w in req for w in ["en passant on"]):
        changes["allow_en_passant"] = True

    if any(w in req for w in ["capture only", "только взятие", "must capture", "обязательное взятие"]):
        changes["capture_only"] = True
    if any(w in req for w in ["normal moves", "обычные ходы", "без обязательных"]):
        changes["capture_only"] = False

    if any(w in req for w in ["no promotion", "без превращения", "запрети превращение"]):
        changes["allow_promotion"] = False
    if any(w in req for w in ["promotion on", "разреши превращение"]):
        changes["allow_promotion"] = True

    for piece in ("queen", "rook", "bishop", "knight", "ферзь", "ладья", "слон", "конь"):
        piece_map = {"ферзь": "queen", "ладья": "rook", "слон": "bishop", "конь": "knight"}
        if piece in req:
            changes["promotion_piece"] = piece_map.get(piece, piece)
            break

    if any(w in req for w in ["inverse", "инверсия", "swap colors", "смени цвета"]):
        changes["inverse_colors"] = True
    if any(w in req for w in ["inverse off", "инверсию выключи"]):
        changes["inverse_colors"] = False

    # Build description
    description_parts = []
    merged = {**current_rules, **changes}
    if not merged.get("allow_castling", True):
        description_parts.append("Без рокировки")
    if not merged.get("allow_en_passant", True):
        description_parts.append("Без взятия на проходе")
    if merged.get("capture_only"):
        description_parts.append("Только взятие")
    if not merged.get("allow_promotion", True):
        description_parts.append("Без превращения")
    elif merged.get("promotion_piece", "queen") != "queen":
        description_parts.append(f"Превращение → {merged['promotion_piece']}")
    if merged.get("inverse_colors"):
        description_parts.append("Инверсия цветов")

    changes["extra_description"] = " | ".join(description_parts) if description_parts else ""
    return changes
