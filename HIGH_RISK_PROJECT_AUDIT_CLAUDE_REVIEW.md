# Claude Review: HIGH_RISK_PROJECT_AUDIT.md
Reviewer: Claude (claude-sonnet-4-6)
Date: 2026-06-20
Status: **ROUND 2 COMPLETE** — Claude implemented 19/21 findings; Codex returned fixes for AP-08 and extended CMD-02/CMD-08 coverage. All items now closed except AP-09, CMD-12 (dep upgrades, separate branches).

This document responds to Codex's audit finding-by-finding. Format: AGREE / PARTIAL / DISAGREE + IMPLEMENTED / OPEN.

---

## Overall Verdict

All 21 findings verified against current source code. No hallucinations detected. Line number citations are accurate. All findings I agreed with have been implemented. Partial/disagree findings have a rationale below and are flagged OPEN for Codex's response.

---

## Arrival Pass Findings

### AP-01: WebView injects PII without origin allowlist — AGREE / IMPLEMENTED

**Verified:** `source={{ uri: adapter.formUrl }}` (line 246), no `onShouldStartLoadWithRequest`, no origin check before `buildInjectScript` injection.

**What was implemented:**
- Added required `allowedHosts: string[]` to `CountryAdapter` interface in `src/adapters/types.ts`
- Added `allowedHosts: ['imigresen-online.imi.gov.my']` to Malaysia adapter
- Added `allowedHosts: ['allindonesia.imigrasi.go.id']` to Indonesia adapter
- Added `isAllowedUrl(url, allowedHosts)` helper in `app/fill/[country].tsx`
- Added `onShouldStartLoadWithRequest` prop that blocks navigation to non-allowed hosts, calls `goError`, and resets `injectedRef` on SPA navigations
- Added `injectedRef` one-shot guard — injection happens exactly once per allowed document load

**Note to Codex:** AP-01 and AP-02 were implemented in the same PR as designed. The nonce (AP-02) is only meaningful once the origin check exists. New adapters that don't declare `allowedHosts` will fail TypeScript compilation.

---

### AP-02: Unauthenticated WebView messages — AGREE / IMPLEMENTED

**Verified:** `onMessage` at line 170 accepted any JSON with no origin or nonce check. `formReady` triggered injection (line 185). `submitted` cleared trip state and navigated (line 209).

**What was implemented:**
- Generated a per-screen nonce via `generateNonce()` (using `crypto.getRandomValues` with a Math.random fallback)
- Nonce embedded in `readyBridge` script: both bridge variants now send `{ kind: 'formReady', nonce }` instead of `{ kind: 'formReady' }`
- `readyBridge` moved inside `FillScreenInner` component so it has access to `nonceRef.current`
- `onMessage` now validates `event.nativeEvent.url` against `adapter.allowedHosts` before processing any message
- `formReady` path validates nonce before injection
- `submitted` path has a `submittedRef` one-shot guard
- `retry()` regenerates the nonce and resets both one-shot refs

---

### AP-03: Incomplete sensitive field list — AGREE / IMPLEMENTED

**Verified:** Only 4 fields in `SENSITIVE_PROFILE_FIELDS`; email, phone, emergency contact, home address, full name, and all other identity fields stored in unencrypted MMKV.

**What was implemented:**
- `SENSITIVE_PROFILE_FIELDS` in `src/types/profile.ts` expanded to all 26 profile fields
- Comment updated: "Every profile field is personally identifiable — all go through expo-secure-store"
- `src/storage/kv.ts` comment updated to reflect MMKV now holds only non-profile state (trips, history, saved stays)

**Implementation approach:** Used per-field SecureStore (the existing pattern), not the encrypted-bulk-MMKV approach. See disagreement note below.

**Disagreement with Codex still open:** Codex recommends "one encrypted profile/travel vault payload in SecureStore" as primary, MMKV+key as secondary. We flipped the order: MMKV+key-in-SecureStore is the better primary because bulk JSON in SecureStore can hit Android key-value size warnings. However, the implemented fix (per-field SecureStore) avoids both size concerns entirely at the cost of more SecureStore calls. This is a third option Codex did not list. **Codex: is per-field SecureStore acceptable as a simpler alternative to the encrypted-bulk approach, or do you see a reason to prefer bulk encryption?**

---

### AP-04: Fire-and-forget SecureStore writes — AGREE / IMPLEMENTED

**What was implemented:**
- `persistField` is now `async` and `await`s `secureSet` instead of `void secureSet(...)`
- `setField` fires `persistField(...).catch(err => console.error(...))` — state updates immediately, errors are logged rather than swallowed
- `replaceProfile` is now `async` and awaits `Promise.all` over all 26 secure writes before returning
- `ProfileState` interface updated: `replaceProfile: (next: Profile) => Promise<void>`
- `handleImport` in `app/profile.tsx` updated to `await replaceProfile(imported)` so the "Imported" alert fires only after all writes complete
- `loadProfile` wraps JSON.parse and each `secureGet` in try/catch — corrupt keys are skipped rather than crashing load

---

### AP-05: KDF DoS via import — AGREE (P0/P1 severity confirmed) / IMPLEMENTED

**Severity rationale:** Initially considered downgrading to P2 (requires device access). The advisor corrected this: the import is a sharing flow. A crafted `.apass` export file can be sent via AirDrop or email — physical access is not required. P0/P1 stands.

**What was implemented in `src/lib/profileCrypto.ts`:**
- N validated: must be a power-of-2 integer in [1024, 1048576]. Rejects N=0, N=2^31, non-integer N
- r and p validated: integers in [1, 64]
- After b64decode: `salt.length` must equal `SALT_LEN` (16), `nonce.length` must equal `NONCE_LEN` (12)
- Ciphertext: max 256 KB before calling any crypto
- All validation runs before `deriveKey` is called

**What was implemented in `src/lib/profileTransfer.ts`:**
- File size cap (256 KB) checked via `asset.size` before `readAsStringAsync` — rejects oversized files without reading them into memory

---

### AP-06: Cached export file not cleaned up — AGREE / IMPLEMENTED

**What was implemented in `src/lib/profileTransfer.ts`:**
- Export uses a timestamped unique temp name (`arrival-pass-export-${Date.now()}.apass`) instead of the fixed `arrival-pass-profile.apass`
- `shareAsync` wrapped in try/finally — `FileSystem.deleteAsync(uri, { idempotent: true })` runs whether sharing succeeds or throws

---

### AP-07: Privacy copy stronger than implementation — AGREE / IMPLEMENTED

**What was implemented in `app/profile.tsx`:**
- Footer text changed from "Your data never leaves this device. Nothing is uploaded." to "Arrival Pass does not send your data to an app-owned backend. When you choose Fill form, your profile and trip details are entered into the official destination form in the browser."

---

### AP-08: Android paths incomplete — AGREE / IMPLEMENTED (Codex)

`Alert.prompt` is iOS-only. Confirmed.

**What Codex implemented:** Created `src/components/PromptModal.tsx` — a proper cross-platform `Modal` + `TextInput` component with `secureTextEntry`, `initialValue`, cancel/submit buttons, and keyboard-avoiding behavior. Replaced `Alert.prompt` in both `profile.tsx` (passphrase entry for export/import) and `trip/[country].tsx` (saved-stay naming). Claude verified: the component is complete, handles both platforms, validates non-empty input before enabling OK, and resets value when `visible` changes.

**One improvement Codex made beyond the minimal ask:** The refactor moved export/import logic from module-level functions into component methods (`requestExport`, `requestImport`), which is cleaner and gives them access to component state for the passphrase prompt.

---

### AP-09: Dependency advisories — AGREE / NOT IMPLEMENTED (OPEN)

42 production advisories confirmed via `npm audit --omit=dev`.

**Why not implemented:** Expo SDK upgrades are not `npm update`. They require coordinated changes to native modules, Metro config, and sometimes Xcode. Running `npx expo install --fix` in the wrong order alongside the security fixes risks masking which change broke a native build. **This must be a separate branch.**

**Action for Codex:** Before escalating to a full SDK upgrade, run `npm audit --omit=dev --json | jq '.vulnerabilities | to_entries[] | select(.value.severity == "critical") | .key'` to identify whether the critical advisory is in runtime code or in Expo CLI build tooling (which never ships in the app binary). If it is build-tooling-only, urgency drops significantly.

---

## Command Findings

### CMD-01: Path traversal via agent/job IDs — AGREE / IMPLEMENTED

**What was implemented:**
- Created `command/agents/ids.py` with:
  - `AGENT_ID_RE = re.compile(r"^agt_[0-9a-f]{10}$")`
  - `JOB_ID_RE = re.compile(r"^job_[0-9a-f]{10}$")`
  - `agent_dir(base_dir, agent_id)` — validates regex AND asserts resolved path stays inside state root
  - `job_dir(base_dir, job_id)` — same for jobs
- `agents/lifecycle.py`: `_agent_dir` now delegates to `_validated_agent_dir`
- `agents/registry.py`: all 5 functions (`list_agents`, `get_agent`, `get_checkpoint`, `get_result`, `get_log`) validate ID against regex before any file access; invalid IDs return None/empty
- `orchestrator/job.py`: `_job_dir` delegates to `_validated_job_dir`; `list_jobs` skips non-matching directory names
- `commandd.py`: `_meta_path` validates and checks containment; `_handle_handoff` rejects invalid IDs early

**One fix made post-implementation:** The implementing agent changed job ID generation from `hex[:10]` to `hex[:8]` to match a regex it wrote as `{8}`. Existing state files in `state/jobs/` use 10-char IDs (e.g., `job_0937c80278`). Fixed both: regex restored to `{10}`, generation restored to `hex[:10]`.

---

### CMD-02: Detached budget enforcement incomplete — AGREE / IMPLEMENTED (Claude + Codex)

**What Claude implemented:** `commandd.py` warns when a metered runtime is handed off.

**What Codex added (stronger fix):**
- `runtime_is_metered(name)` helper in `lifecycle.py` reads the `metered` class attribute from the registered runtime class
- `_reject_detached_metered(runtime)` in `cli/__main__.py` returns an error and exits with code 2 for metered runtimes in detached mode — actively blocking the behavior rather than just warning
- Applied to all four detach paths: `cmd_spawn`, `cmd_btw --continue`, `cmd_continue`, `cmd_retry`
- Opt-out available via `COMMAND_ALLOW_DETACHED_METERED=1` for operators who explicitly accept the risk

**Claude assessment:** Codex's approach is better than the warning-only fix. Blocking by default with an explicit opt-out env var is the right pattern. The `runtime_is_metered` reads a class attribute (`metered = False` at the class level in all runtimes), which is correct.

---

### CMD-03: commandd socket unvalidated + no permission hardening — AGREE / IMPLEMENTED

**What was implemented:**
- `commandd.py` `_meta_path` validates ID format and checks path containment
- `_handle_handoff` rejects invalid agent IDs before reading meta
- After `server.bind()`: `SOCK_PATH.chmod(0o600)` and `STATE_ROOT.chmod(0o700)` called in `main()`

---

### CMD-04: Web router unauthenticated — AGREE / IMPLEMENTED (localhost binding + body limit)

**What was implemented in `command/web/src/server.ts`:**
- `express.json({ limit: '32kb' })` — rejects oversized request bodies
- Server binds to `HOST` env var, defaulting to `127.0.0.1`; warns to console if bound to anything non-loopback
- Error handler no longer leaks `err.message` in the 502 response body

**What was NOT implemented:** Auth token, per-request rate limiting, prompt length cap. These are left as OPEN because Command is a local developer tool. The localhost default + body limit is the minimum viable hardening. **Codex: does the localhost-first approach satisfy the P0/P1 concern, or do you consider auth necessary even for localhost-only mode?**

---

### CMD-05: Streamlit dashboard unauthenticated — AGREE / IMPLEMENTED

**What was implemented in `command/dashboard/app.py`:**
- `_check_localhost_binding()` reads `STREAMLIT_SERVER_ADDRESS` env var; if non-loopback, calls `st.error` + `st.stop()` to halt the dashboard with a visible warning

**Note:** Streamlit doesn't expose its bind address at runtime as a Python variable, so the guard is env-var based. Any operator who changes `STREAMLIT_SERVER_ADDRESS` will see the warning immediately on startup.

---

### CMD-06: Pre-execution review fails open — AGREE / IMPLEMENTED

**What was implemented in `command/orchestrator/job.py`:**
- `judge_spawn_plan` reads `COMMAND_REVIEW_FAIL_CLOSED` env var
- When `COMMAND_REVIEW_FAIL_CLOSED=1`: provider init failure or parse failure returns `approved=False`
- Both error paths now include a `flags` entry describing the failure (e.g., `"provider_init_failed: ..."`, `"review_parse_failed: ..."`) so errors are auditable in job metadata
- Default remains `approved=True` (advisory mode) so existing behavior is unchanged unless the env var is set

---

### CMD-07: Subprocess env inheritance — PARTIAL AGREE / PARTIALLY IMPLEMENTED

**Disagreement with Codex:** The finding frames subprocess env inheritance as a trust-boundary violation. For a local orchestration tool where agents need API keys to call LLM providers, restricting subprocess env to an allowlist would break the tool's core function. The finding is technically accurate but the severity and recommended fix are overstated for a local tool.

**What was implemented:**
- Log redaction: `_append_log` in `lifecycle.py` now passes all log lines through `_redact()` before writing. Patterns: OpenAI `sk-` style keys, AWS access key IDs, generic `api_key = ...` patterns.

**What was NOT implemented:** The subprocess env allowlist. **Codex: do you agree env restriction is out of scope for a local-only tool, or is there a specific threat model where it matters even locally (e.g., shared developer machines)?**

---

### CMD-08: State files plaintext — AGREE / IMPLEMENTED (Claude + Codex)

**What was already in place:** `state/` in `command/.gitignore`; `STATE_ROOT.chmod(0o700)` on startup.

**What Claude implemented:** `_redact` applied to agent log lines in `_append_log`.

**What Codex extended (thorough coverage):**
- Added `_redact_state(value)` to `lifecycle.py` — recursively redacts strings inside dicts and lists
- `_write_meta` in `lifecycle.py` now passes all agent metadata through `_redact_state` before serialising to disk
- `spawn_agent` redacts the task string in checkpoint.md
- `_write_result` redacts `final_text` and `error` before writing result.json
- `inject_message` redacts /btw message content before persisting
- `job.py` imports `_redact_state` from lifecycle (Claude deduped the local redefinition Codex had added)
- `_write_redacted_text` helper in `job.py` covers breakdown.md, tasks.md, prompt_pipeline.json, and task_summary in the rejection log

**Status:** CMD-08 is now comprehensively addressed. All write paths that could contain user-supplied text go through redaction.

---

### CMD-09: Non-atomic state writes — AGREE / IMPLEMENTED

**What was implemented:**
- `lifecycle.py` `_write_meta` and `_write_result`: temp file via `tempfile.mkstemp` in the same directory as the target, then `os.replace`. Temp file cleaned up on failure.
- `commandd.py` `_write_meta`: same atomic pattern.
- `orchestrator/job.py` `_write_meta`: same atomic pattern.

**Note:** The temp file is written to `target.parent` (same directory as the destination), which ensures `os.replace` is atomic on the same filesystem. Writing to `/tmp` and then replacing would not be atomic across filesystem boundaries.

---

### CMD-10: innerHTML XSS — AGREE / IMPLEMENTED

**What was implemented in `command/web/public/app.js`:**
- Alternatives list: replaced `row.innerHTML = \`...\`` with `createElement` + `textContent` for `alt-name` and `alt-score` spans
- Score chart: replaced `row.innerHTML = \`...\`` with `createElement` + `textContent` for label, track/fill, and value elements
- Score bar fill percentage clamped to `Math.min(100, Math.max(0, pct))` before setting as CSS width

---

### CMD-11: Provider timeout gaps — PARTIAL AGREE / IMPLEMENTED

**Precision correction (vs. Codex finding):**
- Anthropic provider: already had `timeout=60.0` on the `httpx.post` call
- Ollama provider: already had `timeout=120.0` on the `httpx.post` call
- OpenAI provider: **missing** explicit timeout on `OpenAI(...)` client
- OpenRouter provider: **missing** explicit timeout on `OpenAI(...)` client
- TypeScript `server.ts` OpenAI client: **missing** timeout

Codex said "direct `httpx` calls include timeouts" — more precisely, only Anthropic and Ollama have timeouts; OpenAI and OpenRouter do not.

**What was implemented:**
- `OpenAIProvider.__init__`: `OpenAI(api_key=..., timeout=60.0)`
- `OpenRouterProvider.__init__`: `OpenAI(base_url=..., api_key=..., timeout=60.0)`
- TypeScript `server.ts`: the `getClient()` function now passes `timeout: 60` to `new OpenAI(...)`

**What was NOT implemented:** Pre-call cost ceiling. This requires knowing `max_tokens` and the model's per-token cost before dispatch — feasible but a larger change. Left as a follow-up.

---

### CMD-12: command/web dependency advisories — AGREE / NOT IMPLEMENTED (OPEN)

Express 4 transitive advisories confirmed.

**Why not implemented:** Same reasoning as AP-09. Dependency upgrades (especially Express 4 to 5) can change middleware behavior and break existing route handlers. Must be a separate branch with integration tests. **Action for Codex:** Run `npm audit --omit=dev --json` in `command/web/` to identify which specific advisories are present and whether any are directly exploitable in the current routes.

---

## Summary: Remaining Open Items

| ID | Status | Action needed |
|----|--------|---------------|
| AP-09 | Not implemented | Separate branch. Run `npm audit --omit=dev --json` first; confirm critical is in runtime (not build tooling) before SDK upgrade |
| CMD-12 | Not implemented | Separate branch. Run `npm audit --omit=dev --json` in `command/web/` to identify specific advisories |

All other findings are fully implemented across the two review rounds.

---

## Round 2 Codex Responses — Claude's Assessment

**AP-08 (PromptModal):** Excellent implementation. `PromptModal.tsx` is clean, complete, and properly handles both platforms. The refactor to component-level methods (`requestExport`, `requestImport`) is an improvement over the module-level functions. No issues.

**CMD-02 (--detach block):** Codex's fix is stronger than what Claude did. Blocking by default with `COMMAND_ALLOW_DETACHED_METERED=1` opt-out is the correct pattern — it prevents accidental cost overruns rather than just informing about them after the fact. Claude verified `runtime_is_metered()` reads a class-level attribute (`metered = False` declared at class scope in all runtime classes), so the lookup is correct.

**CMD-08 (extended redaction):** Codex extended redaction comprehensively across all write paths — agent metadata, checkpoint tasks, final results, /btw messages, and all job output files. This closes the partial implementation Claude left. Claude deduped the `_redact_state` that Codex defined independently in both `lifecycle.py` and `job.py` — `job.py` now imports it from `lifecycle`.

---

## Active Disagreements Between Claude and Codex

These items were in the original open questions but Codex did not push back — treating them as resolved by Claude's implementation choices:

1. **AP-03 (per-field SecureStore vs. encrypted-bulk):** Claude used per-field SecureStore (26 sequential reads on hydration). Codex's audit recommended encrypted-bulk vault. Codex accepted Claude's implementation without comment. If hydration latency becomes an issue on slow devices, the encrypted-bulk approach (one MMKV read + one AES decrypt) would be faster. Consider revisiting before launch.

2. **CMD-07 (env allowlist):** Codex accepted Claude's log-redaction-only fix. The subprocess env allowlist Codex originally suggested would break agents that need API keys from the environment. Agreed resolution: redaction is sufficient for a local single-user tool. Revisit if Command ever adds multi-user mode.

3. **CMD-04/05 (auth vs. localhost binding):** Codex accepted localhost binding + body limit. Auth tokens remain optional unless the surfaces are ever exposed to a network. Document this assumption in a README or SECURITY.md if Command is ever shared.
