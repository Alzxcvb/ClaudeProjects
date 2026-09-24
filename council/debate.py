"""One end-to-end council debate: assign providers (A1), run cases then
rebuttals through an injected runner, judge blind (B1), then insert exactly
one ledger row with a C1 record snapshot -- only after the judge succeeds.

See plan-council.md §5/§7 task 6 and the amendments: A1 (alternation,
replaces §5), A5 (record-aware judge), B1 (blinding), C1 (record snapshot
at insert time).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Tuple, Union

from . import ledger as ledger_mod
from . import prompts
from .runner import CouncilError

PathLike = Union[str, Path]


def assign_providers(n: int) -> Tuple[str, str, str]:
    """A1 (replaces the unamended §5 formula): from the ledger row count n
    (BEFORE this question), returns (provider_a, provider_b,
    judge_provider).

    judge alternates claude/codex every question (n % 2). Side A's
    provider flips every 2 questions (n // 2 parity). Over any 4
    consecutive questions the judge's provider matches side A's provider
    exactly twice and side B's provider exactly twice:
        n=0: A=codex,  B=claude, judge=claude -> matches B
        n=1: A=codex,  B=claude, judge=codex  -> matches A
        n=2: A=claude, B=codex,  judge=claude -> matches A
        n=3: A=claude, B=codex,  judge=codex  -> matches B
    """
    judge_provider = "claude" if n % 2 == 0 else "codex"
    if (n // 2) % 2 == 0:
        provider_a, provider_b = "codex", "claude"
    else:
        provider_a, provider_b = "claude", "codex"
    return provider_a, provider_b, judge_provider


def _map_winner_to_side(verdict_winner: str, position1_side: str) -> str:
    """Maps the judge's "1"/"2" pick back to A/B via the position1_side
    that was chosen (and stored) before the judge prompt was built."""
    if verdict_winner == "1":
        return position1_side
    return "B" if position1_side == "A" else "A"


def run_debate(
    question: str,
    persona_a,
    persona_b,
    runner,
    ledger_path: PathLike,
    rng,
) -> dict:
    """Runs one full debate and inserts exactly one row -- only after the
    judge produces a valid verdict. `persona_a`/`persona_b` are always
    side A / side B (a --pair's order); provider assignment to sides is
    separate (A1) and comes from the ledger row count. `rng` only needs a
    `.choice(seq)` method (random.Random satisfies this; tests may inject
    a smaller double for a deterministic position1_side).

    Raises CouncilError (never inserting a row) if any call fails, or if
    the judge's output still can't be parsed after one retry.
    """
    n = ledger_mod.count(ledger_path)
    provider_a, provider_b, judge_provider = assign_providers(n)

    # C1: snapshot each side's record BEFORE this debate. These are
    # exactly the numbers shown to the judge and exactly the numbers
    # stored -- never recomputed later from current ledger state.
    record_a = ledger_mod.record(ledger_path, persona_a.key)
    record_b = ledger_mod.record(ledger_path, persona_b.key)

    case_system_a, case_prompt_a = prompts.build_case_prompt(persona_a, question)
    case_system_b, case_prompt_b = prompts.build_case_prompt(persona_b, question)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(runner.call, provider_a, case_prompt_a, case_system_a)
        fut_b = pool.submit(runner.call, provider_b, case_prompt_b, case_system_b)
        case_a = fut_a.result()
        case_b = fut_b.result()

    rebuttal_system_a, rebuttal_prompt_a = prompts.build_rebuttal_prompt(
        persona_a, question, case_a, case_b
    )
    rebuttal_system_b, rebuttal_prompt_b = prompts.build_rebuttal_prompt(
        persona_b, question, case_b, case_a
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(runner.call, provider_a, rebuttal_prompt_a, rebuttal_system_a)
        fut_b = pool.submit(runner.call, provider_b, rebuttal_prompt_b, rebuttal_system_b)
        rebuttal_a = fut_a.result()
        rebuttal_b = fut_b.result()

    position1_side = rng.choice("AB")
    if position1_side == "A":
        pos1_case, pos1_rebuttal, pos1_record = case_a, rebuttal_a, record_a
        pos2_case, pos2_rebuttal, pos2_record = case_b, rebuttal_b, record_b
    else:
        pos1_case, pos1_rebuttal, pos1_record = case_b, rebuttal_b, record_b
        pos2_case, pos2_rebuttal, pos2_record = case_a, rebuttal_a, record_a

    judge_prompt = prompts.build_judge_prompt(
        question,
        [persona_a.name, persona_b.name],
        pos1_case,
        pos1_rebuttal,
        pos2_case,
        pos2_rebuttal,
        pos1_record,
        pos2_record,
    )

    judge_raw = runner.call(judge_provider, judge_prompt, prompts.JUDGE_SYSTEM)
    try:
        verdict = prompts.parse_verdict(judge_raw)
    except prompts.VerdictParseError:
        # One retry on bad JSON, with an explicit instruction appended.
        retry_prompt = judge_prompt + "\n\nReturn only JSON, no prose."
        judge_raw = runner.call(judge_provider, retry_prompt, prompts.JUDGE_SYSTEM)
        try:
            verdict = prompts.parse_verdict(judge_raw)
        except prompts.VerdictParseError as exc:
            raise CouncilError(
                f"judge output could not be parsed as JSON after one retry: {exc}"
            ) from exc

    winner_side = _map_winner_to_side(verdict["winner"], position1_side)

    row_id = ledger_mod.insert(
        ledger_path,
        question=question,
        persona_a=persona_a.key,
        persona_b=persona_b.key,
        provider_a=provider_a,
        provider_b=provider_b,
        judge_provider=judge_provider,
        case_a=case_a,
        case_b=case_b,
        rebuttal_a=rebuttal_a,
        rebuttal_b=rebuttal_b,
        position1_side=position1_side,
        winner=winner_side,
        confidence=verdict["confidence"],
        key_reason=verdict["key_reason"],
        would_change_mind=verdict["would_change_mind"],
        judge_raw=judge_raw,
        rec_a_wins=record_a["wins"],
        rec_a_resolved=record_a["resolved"],
        rec_b_wins=record_b["wins"],
        rec_b_resolved=record_b["resolved"],
    )

    return {
        "id": row_id,
        "question": question,
        "persona_a": persona_a,
        "persona_b": persona_b,
        "provider_a": provider_a,
        "provider_b": provider_b,
        "judge_provider": judge_provider,
        "case_a": case_a,
        "case_b": case_b,
        "rebuttal_a": rebuttal_a,
        "rebuttal_b": rebuttal_b,
        "position1_side": position1_side,
        "winner": winner_side,
        "confidence": verdict["confidence"],
        "key_reason": verdict["key_reason"],
        "would_change_mind": verdict["would_change_mind"],
    }
