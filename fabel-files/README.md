# Fabel Files

A portable operating manual distilled from Fable 5's working method, packaged so weaker/cheaper models (Haiku, Sonnet, older Opus, or any other LLM) can borrow the discipline even when they can't borrow the capability.

The core bet: much of what separates a stronger model from a weaker one on real tasks is not knowledge — it's process. Predicting before acting, decomposing by risk, verifying before claiming, knowing when to stop. Process can be written down and followed mechanically. These files write it down.

## Contents

```
fabel-files/
├── CLAUDE-FABEL.md          ← the core manual (load this whole, always)
├── protocols/               ← deep dives, loaded on trigger
│   ├── failure-modes.md     ← catalog of weak-model anti-patterns + countermeasures
│   ├── decomposition.md     ← breaking work down, risk-first ordering
│   ├── verification.md      ← proving work is actually done
│   ├── debugging.md         ← fault isolation procedure
│   └── self-review.md       ← hostile review pass before "done"
├── templates/               ← fill-in files the manual references
│   ├── task-plan.md
│   ├── debug-log.md
│   └── decision-log.md
├── domains/                 ← 13 per-specialty standards files (one per specialist)
│   └── README.md            ← the assignment model + catalog
├── agents/
│   └── coach.md             ← strong-model grading agent: rubric, prompt, coaching loop
└── evals/                   ← 5 fixed benchmark tasks with verified fixtures
    └── README.md            ← run protocol + scoring
```

`CLAUDE-FABEL.md` is self-contained — a model that reads only it gets most of the value. The protocols add depth on trigger (the manual says when to read each one), which keeps the always-loaded context small.

## The specialist architecture

The pieces compose into a training loop for a fleet of cheap specialists:

1. **Specialize**: give each weak model `CLAUDE-FABEL.md` + exactly ONE `domains/<x>.md` (see `domains/README.md` for why one, and the catalog of 13). That pair is the specialist's whole identity.
2. **Measure**: run it on the fixed tasks in `evals/` (fixtures verified, answer keys included) under identical conditions — control vs. manual vs. coached — and log scores in `evals/results-log.md`.
3. **Coach**: one Opus-class model grades each transcript against the manual (`agents/coach.md`) and emits exactly ONE corrective rule per run, appended to that specialist's `learned-rules.md`.
4. **Repeat**: rules compound; eval scores tell you whether they're working. The coach prunes the rule list when it grows past ~10.

The economics: violations are cheap to detect after the fact but expensive to avoid in the moment, so the strong model does the easy judging and the cheap models do the hard doing.

## How to wire it up

Pick one:

1. **Import into a project's CLAUDE.md** (simplest, persistent):
   ```markdown
   @/Users/alexandercoffman/Dev/fabel-files/CLAUDE-FABEL.md
   ```
   Add that line to any project's `CLAUDE.md` and every session in that project loads the manual. Relative paths work too if the folder is copied into the project.

2. **Per-session, any model:**
   ```bash
   claude --model claude-haiku-4-5-20251001 \
     --append-system-prompt "$(cat fabel-files/CLAUDE-FABEL.md)"
   ```

3. **Subagents:** in a `.claude/agents/<name>.md` definition, reference the manual in the agent's prompt body, or paste the core file in. Useful for testing "same task, same model, with vs. without."

4. **Other tools/APIs:** paste `CLAUDE-FABEL.md` as (part of) the system prompt. Nothing in it is Claude Code specific except file paths.

## How to experiment

Use the benchmark: `evals/README.md` has the full protocol (copy fixtures out, fixed wrapper prompt, never show the model a RUBRIC.md) and a two-axis score — outcome (task-specific answer key) and process (generic, from the transcript). The five tasks were chosen to expose the manual's levers: red-before-green debugging, build-to-spec edge cases, data reconciliation, blame-order config debugging, and hostile review against a planted answer key.

The quick informal version is still valid: same model, same prompt, with vs. without the manual, and compare — did it verify before claiming done? Did it stop at 3 attempts or thrash? Is the diff scoped? Are the report's claims labeled and true?

## Honest limits

Procedure captures the discipline gap, not the whole gap. A weaker model with this manual will still miss subtle design tradeoffs, produce less elegant code, and occasionally follow a checklist off a cliff. What the manual mostly buys: fewer false "done" claims, fewer hallucinated APIs, less thrashing, recoverable state when context runs out, and honest reports. That's a large share of what goes wrong in practice.

These files are deliberately generic — no Alex-specific rules — so they stack cleanly on top of the existing global and project CLAUDE.md files without duplicating them, and so experiments aren't confounded by personal preferences.
