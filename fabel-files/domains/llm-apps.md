# Domain: LLM Applications

Applies when: building features powered by language models — prompts, agents, tool use, RAG, structured extraction, evaluation. Load with `CLAUDE-FABEL.md`.

The defining property: the core component is **non-deterministic and confidently wrong by default**. Everything in this file exists because you cannot unit-test your way to trusting a model; you can only measure it and constrain it.

## 1. Failure modes

- **Vibes-driven prompt engineering.** Tweaking a prompt, eyeballing one output, declaring improvement. Without a fixed eval set, prompt changes are a random walk that overfits the last example you looked at.
- **Trusting the output shape.** Parsing model output with no validation, until the day it returns almost-valid JSON, a preamble ("Here's the JSON you asked for:"), or a refusal — and the app crashes or, worse, stores garbage.
- **Hallucination as edge case.** Treating fabrication as rare. It is the default failure mode; the design must assume any unverified claim may be invented.
- **Context stuffing.** Shoveling everything into the prompt because it "might help," inflating cost/latency and burying the signal.
- **Unbudgeted loops.** Agents that can retry/recurse without a cap on iterations, tokens, or dollars.
- **Blaming the model first.** In RAG, blaming generation when retrieval returned the wrong passages. Measure retrieval separately before touching prompts.

## 2. Standards

- **A fixed eval set gates every prompt change.** Minimum ~10 real cases (include the ugly ones that motivated the feature) with expected outcomes. Run before/after any prompt, model, or parameter change; a change ships only if the eval doesn't regress. This is the domain's red-before-green.
- **All model output is untrusted input.** Parse defensively, validate against a schema, and design the failure path (retry with feedback / fallback / surface to user) for output that doesn't conform. Use API-level structured output where available instead of asking nicely.
- **Pin everything**: model ID, temperature, max tokens — in code/config, never implicit defaults. A model upgrade is a deliberate change, run against the eval set.
- **Budgets are explicit**: max tokens per call, max iterations per agent loop, max cost per user action — written in the code, enforced, and logged when hit.
- **Log full request and response** (with secrets redacted) for every call in development and sampled in production; you cannot debug what you didn't capture.
- Tool-use/agent code validates tool arguments like API input (they are), and every tool reports errors back to the model in a form it can act on.
- User-facing claims from the model that assert facts about the user's data must be traceable to provided context, or labeled as generated.

## 3. Defaults

- Smallest model that passes the eval set; escalate model size only on measured failure. Newest model generation over old ones.
- Plain, explicit instructions over clever ones; one job per prompt; examples in the prompt for format-critical output.
- RAG debugging order: (1) is the answer in the corpus? (2) did retrieval fetch it? (3) did the model use it? Fix in that order — most "model is dumb" bugs are (1) or (2).
- Long context beats fine-tuning beats clever prompting for most knowledge problems; fine-tune only with an eval set that proves the need.
- Determinism where possible: temperature 0 for extraction/classification; sampling only where variety is the product.

## 4. Verification

- Run the eval set; quote pass rates before/after. One anecdote is not verification in this domain, ever.
- Adversarial pass: empty input, huge input, non-English, and prompt injection attempts ("ignore previous instructions...") through any user-controlled field — observe containment, not hope.
- Exercise the failure paths deliberately: force a malformed output (or simulate one) and watch the fallback actually engage.
- Check the logs for one full request: is the final assembled prompt what you think it is? (Template bugs hide here — the classic is an empty context slot.)
- Verify cost: tokens per call × expected volume, stated in the report.

## 5. Edge cases that always matter

- Input at/over the context limit; truncation that silently drops the instructions or the newest message.
- The model refusing (safety or confusion) where the app expects data.
- Conversation state: does turn 15 still contain what turn 2 established, or did trimming eat it?
- Concurrent/streamed output: partial JSON, client disconnects mid-stream.
- User content containing your own delimiters/markup (prompt-format injection, even without malice).

## 6. Stop signals

- Accuracy has plateaued across 3 prompt iterations → the lever is elsewhere: data, retrieval, task decomposition, or model — measure which.
- You're adding a rule to the prompt for each new failure ("also never say X") → the prompt is overfitting; restructure the task instead.
- The agent needs more than ~5 sequential autonomous steps to be useful → reliability compounds against you; add checkpoints or a human gate.
- You can't say what the feature's acceptable error rate is → that's a product decision nobody made; surface it before building further.
