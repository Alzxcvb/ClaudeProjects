# Domain: Technical Writing

Applies when: writing READMEs, docs, runbooks, reports, proposals, or any prose meant to transfer understanding or enable action. Load with `CLAUDE-FABEL.md`.

A document is a tool with a job: after reading, a specific person can do a specific thing or hold a correct model they didn't have before. Judge every sentence by whether it serves that job.

## 1. Failure modes

- **Writing from memory.** Documenting commands, paths, and flags without running them. The doc is born stale; the reader hits an error in step 2 and distrusts everything after.
- **Organization by system, not by reader.** Structuring docs around the code's architecture instead of the reader's task. The reader wants "how do I add a widget," not a tour of the module graph.
- **Buried ledes.** The critical fact (what this is, what changed, what you must do) in paragraph four, after the throat-clearing.
- **Curse of knowledge.** Undefined jargon, missing prerequisites, "simply" and "just" in front of steps that aren't. The author can no longer see what a newcomer can't know.
- **Abstraction without examples.** Describing behavior in general terms with zero concrete input/output pairs. One example beats three paragraphs.
- **Docs that rot invisibly.** No versions, no dates, no owner — correct at birth, silently wrong within months, with nothing signaling the reader to distrust it.

## 2. Standards

- **Every command was actually run; every path, flag, and output shown is real.** Copy from the terminal, never from memory. This is the domain's verification core, and it is not optional.
- The first three sentences state: what this is, who it's for, what they'll be able to do. The reader can decide to stop reading — that's a feature.
- Structure follows the reader's task order, with headings a scanner can use ("Add a new endpoint," not "Miscellaneous notes").
- Every abstract claim is followed by a concrete example; every procedure shows expected output so the reader can tell success from failure at each step.
- Prerequisites are explicit and testable ("requires Node 20+: check with `node --version`"), stated before the first step, not discovered at step 5.
- Anything that rots carries metadata: versions it applies to, date last verified. Anything with a decision carries the why, not just the what (the why is what survives refactors).
- Plain language: short sentences, active voice, no word a newcomer to this codebase would need to look up unless the doc defines it.

## 3. Defaults

- Pick the document's type and stay in it — tutorial (learning by doing), how-to (task recipe), reference (lookup), explanation (understanding). Mixing types is how docs bloat; link between them instead.
- README skeleton: what it is (1 paragraph) → quickstart that WORKS (the 5 commands from clone to running) → common tasks → where things live. Depth goes in linked docs, not the README.
- Runbook skeleton: symptom → check → action, in the order the 3am responder needs them; commands copy-pasteable with placeholders clearly marked.
- Reports (per the core manual): outcome first, evidence attached, calibration labels intact. Length is set by what the reader needs to decide, not by effort performed.
- Update the doc nearest the change in the same diff; a behavior change with no doc change is an incomplete diff when docs cover that behavior.

## 4. Verification

- **Follow your own doc, literally, in a clean environment** — fresh clone, fresh shell, no reliance on your session's state. Every step, every command, exactly as written. Where you deviated "because you knew better," the doc is wrong; fix it.
- Check every fact against its source of truth: version numbers against lockfiles, paths against the tree, API shapes against the code — not against recollection.
- Read it aloud once: where you stumble, the reader stops.
- Scan headings alone: do they tell the story? A scanner is most of your audience.
- For instructions handed to others: watch (or simulate coldly) one execution by someone who isn't you; their first confusion is your first bug.

## 5. Edge cases that always matter

- The reader on a different OS/shell/version than the author — state assumptions, don't embed them silently.
- Failure paths: what the reader does when a step errors (the most common real-world doc need, and the least documented).
- Copy-paste hazards: smart quotes, line-wrapped commands, prompts (`$`) that get pasted along with the command.
- Placeholders: make them unmistakable (`<YOUR_API_KEY>`) and say where the real value comes from.
- Secrets in examples: real tokens/URLs pasted from the author's terminal into the doc — scan for this every time, it's a leak with a long shelf life.

## 6. Stop signals

- You're explaining the code's internals to justify a step → the reader needed the step, not the tour; cut it or move it to an explanation doc.
- The how-to has grown branches ("if X, do Y, unless Z") → it's two documents, or the underlying process is broken and the fix isn't prose.
- You can't name the specific reader → you'll write for everyone and serve no one; get the audience defined before writing more.
- The doc is a warning about behavior ("NEVER call this with null") → where possible, fix the behavior or add the guard in code; a doc is the weakest place to store an invariant.
