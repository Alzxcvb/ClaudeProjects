from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .academic_extractor import (
    extract_coordinate_mentions,
    slugify,
    ensure_parent,
    write_json,
    write_csv,
)


@dataclass
class ExtractionConfig:
    output_prefix: str = "sites"
    use_claude: bool = False
    model: str = "claude-haiku-4-5-20251001"


# Regex patterns for historical site mentions
SITE_PATTERNS = [
    r"(?:the\s+)?(?:ancient\s+)?(?:ruins?\s+of\s+)?(?P<site>[A-Z][a-zA-Z\s\-\']+?)(?:\s+(?:temple|city|tomb|palace|settlement|fort|monument|cave|necropolis|harbor|site|ruins?))",
    r"(?P<site>[A-Z][a-zA-Z\s\-\']+?)\s+(?:temple|city|tom?b|palace|settlement|fort|monument|cave|necropolis|harbor)",
    r"(?:the\s+)?(?P<site>[A-Z][a-zA-Z\s\-\']+?)\s+(?:pyramid|ziggurat|cathedral|basilica|fortress|citadel)",
]

COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in SITE_PATTERNS]

# Keywords that indicate archaeological/historical context
CONTEXT_KEYWORDS = {
    "ancient", "archaeological", "excavation", "excavated", "discovered", "ruins",
    "temple", "city", "tomb", "palace", "monument", "site", "settlement", "fort",
    "pyramid", "ziggurat", "cathedral", "artifact", "civilization", "period",
}

GENERIC_SITE_NAMES = {
    "discover",
    "discovery",
    "discoveries",
    "hidden",
    "unknown",
    "forgotten",
    "untouched",
    "uncharted",
    "latest archaeological",
    "latest archaeological discoveries",
}

GENERIC_PREFIX_WORDS = {
    "a",
    "an",
    "and",
    "but",
    "discover",
    "explore",
    "exploring",
    "find",
    "found",
    "forgotten",
    "hidden",
    "i",
    "its",
    "latest",
    "lost",
    "my",
    "our",
    "some",
    "that",
    "the",
    "these",
    "this",
    "those",
    "unknown",
    "unmarked",
    "untouched",
    "we",
    "well",
}

GENERIC_FRAGMENT_PATTERNS = (
    "we'll",
    "we will",
    "join me",
    "pieces of our past",
    "special access",
    "latest archaeological discoveries",
    "only known to locals",
)

COMMON_ENGLISH_WORDS = {
    "a", "about", "after", "all", "along", "already", "also", "although", "am", "an",
    "and", "another", "any", "are", "around", "as", "at", "be", "because", "been",
    "before", "being", "believe", "best", "between", "both", "brief", "but", "by",
    "called", "can", "city", "complex", "construction", "could", "couple", "culture",
    "cultures", "dating", "definitely", "did", "discover", "discovered", "discovery",
    "do", "document", "dozens", "down", "earliest", "evidence", "excavated",
    "expedition", "explore", "exploring", "far", "find", "first", "forgotten", "found",
    "from", "further", "go", "going", "had", "happening", "have", "he", "here", "hidden",
    "history", "hope", "how", "i", "if", "in", "into", "investigated", "is", "it",
    "its", "join", "just", "known", "latest", "learn", "like", "locals", "look", "lost",
    "made", "make", "many", "media", "modern", "monumental", "more", "most", "my",
    "navigate", "new", "not", "of", "oldest", "on", "one", "only", "open", "or", "our",
    "out", "own", "past", "people", "pieces", "place", "places", "pop", "purpose",
    "reality", "regions", "release", "repurposing", "ruin", "ruins", "same", "saw",
    "secret", "seeing", "share", "site", "sites", "some", "special", "structures",
    "sudden", "supposed", "that", "the", "their", "them", "there", "these", "they",
    "thing", "this", "those", "through", "time", "to", "true", "unknown", "unmarked",
    "untouched", "up", "use", "valley", "very", "video", "was", "we", "well", "went",
    "what", "when", "where", "which", "while", "who", "will", "with", "work", "world",
    "would", "you", "your", "youre",
}


def extract_candidate_sites(text: str) -> list[dict[str, Any]]:
    """
    Extract candidate historical sites from transcript text using regex patterns.
    Returns list of {site_name, context_snippet, match_position}.
    """
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for pattern in COMPILED_PATTERNS:
        for match in pattern.finditer(text):
            site_name = match.group("site").strip()

            # Skip very short or generic names
            if len(site_name) < 3 or site_name.lower() in {"the", "and", "this", "that"}:
                continue

            # Normalize: title case, single spaces
            site_name = " ".join(site_name.split()).title()

            # Skip duplicates within this extraction
            if site_name in seen:
                continue
            seen.add(site_name)

            # Extract context snippet (50 chars before and 100 after)
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 100)
            snippet = text[start:end].strip()

            candidates.append({
                "site_name": site_name,
                "context_snippet": snippet,
                "match_position": match.start(),
            })

    return candidates


def is_plausible_site_name(name: str, context_snippet: str) -> bool:
    """Reject generic phrases that match the regex but are not site names."""
    normalized = " ".join(name.lower().split())
    if normalized in GENERIC_SITE_NAMES:
        return False

    words = normalized.split()
    if not words:
        return False

    if len(words) > 5:
        return False

    if words[0] in GENERIC_PREFIX_WORDS:
        return False

    if len(words) == 1 and words[0] in CONTEXT_KEYWORDS:
        return False

    non_common_words = [word for word in words if word not in COMMON_ENGLISH_WORDS]
    if not non_common_words:
        return False

    context_lower = context_snippet.lower()
    if any(fragment in context_lower for fragment in GENERIC_FRAGMENT_PATTERNS):
        return False

    return True


def normalize_site_name(name: str) -> str:
    """Normalize a site name for deduplication (lowercase, strip punctuation, handle aliases)."""
    normalized = name.lower().strip()
    # Remove common suffixes
    normalized = re.sub(r"\s+(ruins?|temple|city|site|complex)$", "", normalized)
    # Remove punctuation
    normalized = re.sub(r"['\-–—]", "", normalized)
    return normalized


def extract_sites_from_transcripts(
    transcripts: list[dict[str, str]], use_claude: bool = False
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Extract historical sites from a list of transcripts.

    Args:
        transcripts: List of {video_id, title, transcript_text} dicts
        use_claude: If True, use Claude API for extraction (requires ANTHROPIC_API_KEY)

    Returns:
        (site_rows, per_video_rows) where:
        - site_rows: deduplicated sites across all videos
        - per_video_rows: each site mention per video
    """
    per_video_rows: list[dict[str, Any]] = []
    site_mentions: dict[str, list[dict[str, Any]]] = {}  # normalized_name -> list of mentions

    for transcript in transcripts:
        video_id = transcript.get("video_id", "")
        title = transcript.get("title", "")
        transcript_text = transcript.get("transcript_text", "")

        if not transcript_text:
            continue

        # Extract candidate sites using regex (Phase 1)
        candidates = extract_candidate_sites(transcript_text)

        # Also check for coordinate mentions
        coordinates = extract_coordinate_mentions(transcript_text)

        for candidate in candidates:
            site_name = candidate["site_name"]
            if not is_plausible_site_name(site_name, candidate["context_snippet"]):
                continue
            normalized = normalize_site_name(site_name)

            per_video_rows.append({
                "video_id": video_id,
                "video_title": title,
                "site_name": site_name,
                "context_snippet": candidate["context_snippet"],
                "match_position": candidate["match_position"],
            })

            # Aggregate by normalized name
            if normalized not in site_mentions:
                site_mentions[normalized] = []
            site_mentions[normalized].append({
                "video_id": video_id,
                "video_title": title,
                "site_name": site_name,
                "context_snippet": candidate["context_snippet"],
            })

    # Build deduped site rows
    site_rows: list[dict[str, Any]] = []
    for normalized_name, mentions in sorted(site_mentions.items()):
        # Use the first (most canonical) site name variant
        canonical_name = mentions[0]["site_name"]

        # Collect all video mentions
        video_ids = list(set(m["video_id"] for m in mentions))
        mention_count = len(mentions)

        site_rows.append({
            "site_name": canonical_name,
            "normalized_name": normalized_name,
            "mention_count": mention_count,
            "video_count": len(video_ids),
            "first_video_id": mentions[0]["video_id"],
            "first_video_title": mentions[0]["video_title"],
            "all_video_ids": "; ".join(video_ids),
            "sample_context": mentions[0]["context_snippet"][:200],
        })

    return site_rows, per_video_rows


@dataclass
class TimedSiteMention:
    site_name: str
    normalized_name: str
    video_id: str
    video_title: str
    start_seconds: float
    end_seconds: float
    context_snippet: str
    match_position: int


def _build_text_and_offsets(words: list[dict[str, Any]]) -> tuple[str, list[tuple[int, int, int]]]:
    """Join words with spaces. Return (text, spans) where spans[i] = (word_idx, char_start, char_end)."""
    parts: list[str] = []
    spans: list[tuple[int, int, int]] = []
    cursor = 0
    for idx, w in enumerate(words):
        token = (w.get("text") or "").strip()
        if not token:
            continue
        if parts:
            parts.append(" ")
            cursor += 1
        spans.append((idx, cursor, cursor + len(token)))
        parts.append(token)
        cursor += len(token)
    return "".join(parts), spans


def _word_at_char(spans: list[tuple[int, int, int]], char_pos: int) -> int | None:
    """Binary search-ish linear scan to find the word index containing char_pos. Small N is fine."""
    for word_idx, start, end in spans:
        if start <= char_pos < end:
            return word_idx
        if char_pos < start:
            return word_idx
    return spans[-1][0] if spans else None


def extract_sites_from_words(
    words: list[dict[str, Any]],
    video_id: str,
    video_title: str,
) -> list[TimedSiteMention]:
    """Extract site mentions with timestamp ranges from a word-level transcript.

    Each word dict must have keys: text, start_seconds, end_seconds.
    """
    if not words:
        return []

    text, spans = _build_text_and_offsets(words)
    candidates = extract_candidate_sites(text)

    mentions: list[TimedSiteMention] = []
    seen_normalized: set[str] = set()

    for cand in candidates:
        site_name = cand["site_name"]
        if not is_plausible_site_name(site_name, cand["context_snippet"]):
            continue

        normalized = normalize_site_name(site_name)
        key = f"{normalized}@{cand['match_position']}"
        if key in seen_normalized:
            continue
        seen_normalized.add(key)

        match_start = cand["match_position"]
        match_end = match_start + len(site_name)
        start_word = _word_at_char(spans, match_start)
        end_word = _word_at_char(spans, max(match_end - 1, match_start))

        if start_word is None or end_word is None:
            continue

        start_seconds = float(words[start_word].get("start_seconds") or 0.0)
        end_seconds = float(words[end_word].get("end_seconds") or start_seconds)

        mentions.append(
            TimedSiteMention(
                site_name=site_name,
                normalized_name=normalized,
                video_id=video_id,
                video_title=video_title,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                context_snippet=cand["context_snippet"],
                match_position=match_start,
            )
        )

    return mentions


def stub_claude_extraction(
    transcripts: list[dict[str, str]], model: str = "claude-haiku-4-5-20251001"
) -> list[dict[str, Any]]:
    """
    Stub for Claude API extraction. When ANTHROPIC_API_KEY is set, this will
    use Claude to extract archaeological sites with full metadata (location, period, etc.).

    For now, returns empty list. Enable by setting --use-claude flag and configuring
    an ANTHROPIC_API_KEY environment variable.
    """
    return []


def run_extraction(
    config: ExtractionConfig,
    transcripts: list[dict[str, str]],
    root: Path,
) -> dict[str, Path]:
    """
    Extract historical sites from transcripts.

    Args:
        config: ExtractionConfig with output settings
        transcripts: List of {video_id, title, transcript_text} dicts from youtube_extractor
        root: Project root path

    Returns:
        Dict of output file paths
    """
    print(f"Extracting sites from {len(transcripts)} transcripts...")

    # Extract sites using regex (always)
    site_rows, per_video_rows = extract_sites_from_transcripts(transcripts, use_claude=False)

    # Optional: Extract using Claude if flag is set and API key available
    if config.use_claude:
        print("Claude extraction not yet implemented. Using regex-only extraction.")

    slug = slugify(config.output_prefix)

    sites_csv = root / "data" / "interim" / "youtube" / f"{slug}_sites_master.csv"
    per_video_csv = root / "data" / "interim" / "youtube" / f"{slug}_sites_per_video.csv"
    summary_json = root / "data" / "interim" / "youtube" / f"{slug}_sites_summary.json"

    write_csv(sites_csv, site_rows)
    write_csv(per_video_csv, per_video_rows)

    summary = {
        "extraction_method": "regex-based" if not config.use_claude else "claude-ai",
        "unique_sites": len(site_rows),
        "total_mentions": len(per_video_rows),
        "transcripts_processed": len(transcripts),
        "output_files": {
            "sites_master_csv": str(sites_csv),
            "sites_per_video_csv": str(per_video_csv),
        },
    }
    write_json(summary_json, summary)

    return {
        "sites_master_csv": sites_csv,
        "sites_per_video_csv": per_video_csv,
        "summary_json": summary_json,
    }
