"""Council CLI: `python3 -m council ask|resolve|history`.

`ask` wires personas -> prompts -> debate -> ledger insert (plan-council.md
§7 task 7). The A3/C2/E2 spend guard, argument parsing (including the E3
--question-file escape hatch), and resolve/history against ledger.py were
built in earlier tasks (1-4) and are unchanged here.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import debate as debate_mod
from . import ledger as ledger_mod
from . import personas as personas_mod
from . import router as router_mod
from . import runner as runner_mod
from .runner import SubprocessRunner

DEFAULT_LEDGER_PATH = Path(__file__).resolve().parent / "ledger.db"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="council", description="Judged two-provider debate.")
    sub = parser.add_subparsers(dest="command")

    ask_p = sub.add_parser("ask", help="Ask the council a question")
    q_group = ask_p.add_mutually_exclusive_group(required=True)
    q_group.add_argument("question", nargs="?", default=None, help="the question, as one argument")
    q_group.add_argument(
        "--question-file",
        dest="question_file",
        default=None,
        help="read the question from this file instead (E3: avoids shell quoting issues)",
    )
    ask_p.add_argument("--pair", default=None, help="persona1,persona2 (default: bull,bear)")

    resolve_p = sub.add_parser("resolve", help="Record a real-world outcome for a question")
    resolve_p.add_argument("id", type=int)
    resolve_p.add_argument("outcome", help="A, B, or neither")

    sub.add_parser("history", help="Show track record and recent questions")

    return parser


def _read_question(args: argparse.Namespace) -> str:
    if args.question_file:
        return Path(args.question_file).read_text().strip()
    return args.question


def _cmd_resolve(args: argparse.Namespace, path: Path) -> int:
    try:
        previous = ledger_mod.resolve(path, args.id, args.outcome)
    except ledger_mod.LedgerError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"question {args.id}: outcome set to {args.outcome} (was {previous!r})")
    return 0


def _format_history(stats: dict) -> str:
    if stats["total_rows"] == 0:
        return "no questions yet"

    lines = [
        f"{stats['total_rows']} questions asked, {stats['resolved_total']} resolved",
        "",
        "Persona record (resolved A/B rows only):",
    ]
    for name, rec in stats["personas"].items():
        if rec["resolved"] == 0:
            lines.append(f"  {name}: no resolved record")
        else:
            lines.append(f"  {name}: {rec['wins']}/{rec['resolved']} wins ({rec['rate']:.0%})")

    judge = stats["judge"]
    lines.append("")
    if judge["accuracy_n"]:
        lines.append(f"Judge accuracy: {judge['accuracy']:.0%} over {judge['accuracy_n']} resolved rows")
    else:
        lines.append("Judge accuracy: no resolved record yet")
    if judge["brier_n"]:
        lines.append(f"Judge Brier score: {judge['brier']:.3f} (lower is better)")
    else:
        lines.append("Judge Brier score: no resolved record yet")
    if judge["same_side_total"]:
        lines.append(
            f"Judge picked its own provider's side {judge['same_side_matches']} of "
            f"{judge['same_side_total']} times"
        )

    better = stats["better_record_followed"]
    if better["total"]:
        lines.append(
            f"Judge followed the side with the better record {better['matches']} of "
            f"{better['total']} times"
        )

    lines.append("")
    lines.append("Last questions:")
    for row in stats["last_rows"]:
        lines.append(f"  #{row['id']} [{row['outcome'] or 'unresolved'}] {row['question'][:60]}")

    return "\n".join(lines)


def _cmd_history(args: argparse.Namespace, path: Path) -> int:
    stats = ledger_mod.history(path)
    print(_format_history(stats))
    return 0


def _format_position_key(result: dict) -> str:
    """The judge saw the sides as Position 1/2 in random order; its reason
    text uses those labels, so say which is which."""
    p1 = result["position1_side"]
    p2 = "B" if p1 == "A" else "A"
    name = {"A": result["persona_a"].name, "B": result["persona_b"].name}
    return (f"(Judge saw Position 1 = Side {p1} {name[p1]}, "
            f"Position 2 = Side {p2} {name[p2]})")


def _format_ask_result(result: dict) -> str:
    persona_a = result["persona_a"]
    persona_b = result["persona_b"]
    winner_side = result["winner"]
    winner_persona = persona_a if winner_side == "A" else persona_b

    lines = [
        f"question #{result['id']}: {result['question']}",
        "",
        f"Side A: {persona_a.name} (via {result['provider_a']})",
        f"Side B: {persona_b.name} (via {result['provider_b']})",
        f"Judge: {result['judge_provider']}",
        _format_position_key(result),
        "",
        f"Winner: Side {winner_side}, {winner_persona.name}",
        f"Confidence: {result['confidence']:.0%}",
        f"Key reason: {result['key_reason']}",
        f"Would change its mind if: {result['would_change_mind']}",
        "",
        f"Resolve later with: /council resolve {result['id']} A|B|neither",
    ]
    return "\n".join(lines)


def main(
    argv: Optional[Sequence[str]] = None,
    runner: Optional[object] = None,
    ledger_path: Optional[Path] = None,
    rng: Optional[random.Random] = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # A3, first line of guard logic: env key check for EVERY subcommand.
    reason = runner_mod.check_env_keys()
    if reason:
        print(reason, file=sys.stderr)
        return 2

    path = ledger_path or DEFAULT_LEDGER_PATH

    if args.command == "resolve":
        return _cmd_resolve(args, path)

    if args.command == "history":
        return _cmd_history(args, path)

    if args.command == "ask":
        active_runner = runner or SubprocessRunner()
        # A3/C2: login-status checks only for ask, via the runner so tests
        # can fake them.
        auth_reason = active_runner.check_auth()
        if auth_reason:
            print(auth_reason, file=sys.stderr)
            return 2
        try:
            question = _read_question(args)
        except OSError as exc:
            print(f"could not read --question-file: {exc}", file=sys.stderr)
            return 1

        # router.py hook (brief-council.md "Out"): v1 always returns
        # "council"; a future Jev gate can branch on this.
        router_mod.route(question)

        try:
            persona_a, persona_b = personas_mod.parse_pair(args.pair)
        except personas_mod.PersonaError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        active_rng = rng if rng is not None else random.Random()

        try:
            result = debate_mod.run_debate(
                question, persona_a, persona_b, active_runner, path, active_rng
            )
        except runner_mod.CouncilError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print(_format_ask_result(result))
        return 0

    parser.print_help()  # pragma: no cover - unreachable with a valid subparser set
    return 0


if __name__ == "__main__":
    sys.exit(main())
