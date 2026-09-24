"""Prompt builders and judge-output parsing for council.

Case/rebuttal builders and the judge builder implement plan-council.md §3
as amended by A5 (the judge weighs argument quality AND each side's
track record, and must say in key_reason how much the record mattered)
and B1 (blinding: provider tokens are scrubbed as case-insensitive
substrings; persona names are only scrubbed when they appear in a
self-reference pattern, not on every bare mention -- "the bull market is
strong" must survive untouched under a persona named Bull).
"""
from __future__ import annotations

import json
import re
from typing import Dict, Iterable, Optional, Tuple

CASE_WORD_CAP = 300
REBUTTAL_WORD_CAP = 200

NO_NAMING_RULE = (
    "Write in the first person. Do not name your persona, your model, or "
    "your provider."
)

JUDGE_SYSTEM = (
    "You are an impartial judge reviewing an anonymous debate. You were "
    "not told and must not guess which model or persona produced either "
    "side. Reply with only the requested JSON object: no prose, no "
    "markdown code fences, no commentary before or after it."
)

# B1: provider tokens, case-insensitive, scrubbed as substrings of a word
# (not whole-word matches) -- covers "ChatGPT", "GPT-5", "Anthropic's", etc.
_PROVIDER_PATTERN = re.compile(
    r"(chatgpt|gpt-?\d*|claude|codex|anthropic|openai|sonnet|opus|haiku)",
    re.IGNORECASE,
)


class VerdictParseError(Exception):
    """Raised when the judge's raw output can't be parsed into a valid
    verdict dict (garbage text, malformed JSON, or a value outside the
    allowed schema)."""


def _self_reference_pattern(persona_name: str) -> "re.Pattern":
    # B1: only a self-reference intro ("I am the Bull", "As the Bull",
    # "speaking as Bull") is redacted -- a bare mention of the name
    # elsewhere in the text is left alone.
    escaped = re.escape(persona_name)
    return re.compile(
        rf"\b(?:(?:I am|I'm|speaking as)\s+(?:the\s+)?{escaped}\b|as\s+(?:the\s+)?{escaped}\b(?![ \t]+(?-i:(?!(?:and|but|so|or|i)\b)[a-z])))",
        re.IGNORECASE,
    )


def blind(text: str, persona_names: Iterable[str]) -> str:
    """B1: scrub provider tokens everywhere, and scrub only self-reference
    mentions of each given persona name. Never whole-word-scrubs persona
    names generally, so normal words that collide with a persona name
    (e.g. "bull market") survive."""
    scrubbed = _PROVIDER_PATTERN.sub("[redacted]", text)
    for name in persona_names:
        if not name:
            continue
        scrubbed = _self_reference_pattern(name).sub("as [redacted]", scrubbed)
    return scrubbed


def build_case_prompt(persona, question: str) -> Tuple[str, str]:
    """Returns (system, prompt) for the case phase. system is the
    persona's worldview body; prompt is the question plus instructions."""
    system = persona.body
    prompt = (
        f"Question: {question}\n\n"
        f"Argue the position your worldview implies, at most {CASE_WORD_CAP} "
        f"words. {NO_NAMING_RULE}"
    )
    return system, prompt


def build_rebuttal_prompt(
    persona, question: str, own_case: str, opposing_case: str
) -> Tuple[str, str]:
    """Returns (system, prompt) for the rebuttal phase."""
    system = persona.body
    prompt = (
        f"Question: {question}\n\n"
        f"Your case:\n{own_case}\n\n"
        f"An opposing analyst wrote:\n{opposing_case}\n\n"
        f"Rebut in at most {REBUTTAL_WORD_CAP} words. {NO_NAMING_RULE}"
    )
    return system, prompt


def _record_sentence(position_label: str, record: Dict[str, Optional[float]]) -> str:
    resolved = record.get("resolved", 0)
    wins = record.get("wins", 0)
    if not resolved:
        return f"{position_label}'s author has no resolved record yet."
    return (
        f"{position_label}'s author has a resolved record of {wins} wins "
        f"in {resolved} resolved questions."
    )


def build_judge_prompt(
    question: str,
    persona_names: Iterable[str],
    position1_case: str,
    position1_rebuttal: str,
    position2_case: str,
    position2_rebuttal: str,
    position1_record: Dict[str, Optional[float]],
    position2_record: Dict[str, Optional[float]],
) -> str:
    """Builds the full judge prompt. Every argument body is run through
    blind() (B1) before it is embedded, using BOTH personas' names --
    either side's text could leak either name, and a leak must be caught
    regardless of which side it came from."""
    names = list(persona_names)
    p1_case = blind(position1_case, names)
    p1_rebuttal = blind(position1_rebuttal, names)
    p2_case = blind(position2_case, names)
    p2_rebuttal = blind(position2_rebuttal, names)

    record_block = "\n".join(
        [
            "Track record (weak prior, resolved questions only):",
            _record_sentence("Position 1", position1_record),
            _record_sentence("Position 2", position2_record),
        ]
    )

    return (
        f"Two anonymous analysts, Position 1 and Position 2, debated: {question}\n\n"
        f"Position 1's case:\n{p1_case}\n\n"
        f"Position 1's rebuttal:\n{p1_rebuttal}\n\n"
        f"Position 2's case:\n{p2_case}\n\n"
        f"Position 2's rebuttal:\n{p2_rebuttal}\n\n"
        f"{record_block}\n\n"
        "Judge on argument quality and likely correctness. Weigh two "
        "things: which case is better argued, and each author's track "
        "record on resolved questions. Say in key_reason how much the "
        "record mattered.\n\n"
        "Return only JSON with exactly this shape, no other text:\n"
        '{"winner": "1" or "2", "confidence": a number 0 to 1, '
        '"key_reason": a short string, "would_change_mind": a short string}'
    )


def parse_verdict(raw_text: str) -> dict:
    """Parses the judge's raw output into a verdict dict. Handles a fenced
    block (```json ... ```), a bare JSON object, or text with prose around
    it, by taking the first "{" to the last "}" in the whole string (plan
    §3). Raises VerdictParseError on anything that isn't valid JSON, isn't
    an object, or fails the winner/confidence schema checks."""
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise VerdictParseError(f"no JSON object found in judge output: {raw_text!r}")

    candidate = raw_text[start : end + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise VerdictParseError(f"could not parse judge JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise VerdictParseError(f"judge JSON is not an object: {data!r}")

    winner = data.get("winner")
    if winner not in ("1", "2"):
        raise VerdictParseError(f"winner must be '1' or '2', got {winner!r}")

    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise VerdictParseError(f"confidence must be a number, got {confidence!r}")
    confidence = float(confidence)
    if not (0.0 <= confidence <= 1.0):
        raise VerdictParseError(f"confidence out of range [0,1]: {confidence}")

    key_reason = data.get("key_reason")
    if not isinstance(key_reason, str) or not key_reason.strip():
        raise VerdictParseError(f"key_reason missing or not a non-empty string: {key_reason!r}")

    would_change_mind = data.get("would_change_mind")
    if not isinstance(would_change_mind, str) or not would_change_mind.strip():
        raise VerdictParseError(
            f"would_change_mind missing or not a non-empty string: {would_change_mind!r}"
        )

    return {
        "winner": winner,
        "confidence": confidence,
        "key_reason": key_reason,
        "would_change_mind": would_change_mind,
    }
