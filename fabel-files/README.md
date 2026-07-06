# Fabel Files

A portable operating manual distilled from Fable 5's working method, packaged so weaker/cheaper models (Haiku, Sonnet, older Opus, or any other LLM) can borrow the discipline even when they can't borrow the capability.

The core bet: much of what separates a stronger model from a weaker one on real tasks is not knowledge — it's process. Predicting before acting, decomposing by risk, verifying before claiming, knowing when to stop. Process can be written down and followed mechanically. These files write it down.

## Contents

```
fabel-files/
├── CLAUDE-FABEL.md          ← the core manual (load this whole)
├── protocols/               ← deep dives, loaded on trigger
│   ├── failure-modes.md     ← catalog of weak-model anti-patterns + countermeasures
│   ├── decomposition.md     ← breaking work down, risk-first ordering
│   ├── verification.md      ← proving work is actually done
│   ├── debugging.md         ← fault isolation procedure
│   └── self-review.md       ← hostile review pass before "done"
└── templates/               ← fill-in files the manual references
    ├── task-plan.md
    ├── debug-log.md
    └── decision-log.md
```

`CLAUDE-FABEL.md` is self-contained — a model that reads only it gets most of the value. The protocols add depth on trigger (the manual says when to read each one), which keeps the always-loaded context small.

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

The clean test is A/B on the same model:

1. Pick a task with a checkable outcome (a bug with a failing test, a small feature with a spec).
2. Run it with a cheap model, no manual. Save the transcript and diff.
3. Fresh session, same model + manual. Same prompt.
4. Compare: did it verify before claiming done? Did it thrash or stop at 3 attempts? Is the diff smaller and scoped? Did the report label verified vs. guess?

Tasks where the manual should visibly help: debugging (the tripwires), multi-step builds (risk-first ordering + task file), anything where the model usually says "this should work now."

## Honest limits

Procedure captures the discipline gap, not the whole gap. A weaker model with this manual will still miss subtle design tradeoffs, produce less elegant code, and occasionally follow a checklist off a cliff. What the manual mostly buys: fewer false "done" claims, fewer hallucinated APIs, less thrashing, recoverable state when context runs out, and honest reports. That's a large share of what goes wrong in practice.

These files are deliberately generic — no Alex-specific rules — so they stack cleanly on top of the existing global and project CLAUDE.md files without duplicating them, and so experiments aren't confounded by personal preferences.
