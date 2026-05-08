# AGENTS.md — Alex Workout

Discoveries and conventions accumulated across iterations. Append, don't rewrite.

---

## Initial knowledge (seeded 2026-05-08)

### File map
- `index.html` — Program landing
- `push.html`, `pull.html`, `legs.html`, `abs.html`, `recovery.html` — session pages
- `progress.html` — log + chart (uses `tracker.js`)
- `references.html` — exercise references
- `style.css` — dark theme, CSS vars
- `tracker.js` — localStorage CRUD + canvas chart (~290 lines)

### CSS variables
Read top of `style.css` for the full list. Key vars referenced in tracker.js: `--text`, `--text-dim`. Match these when adding new UI.

### localStorage shape
- Key: `alex-workout-log`
- Value: JSON array of `{ id, timestamp, session, exercise, weight, reps, sets, notes }`
- Schema MUST stay backward-compatible. Add optional fields only.

### EXERCISES constant
Hardcoded in `tracker.js`. Mirrors what each session page expects. If you add an exercise to a session HTML, add it here too.

### Color accents
- Yellow `#c9a227` — chart line, primary accent
- Grays `#888`, `#2a2a2a` — text-dim, grid lines
- Background `#000`, body text near-white

### Verification commands
- JS: `node --check <file>.js`
- HTML: confirm `<!DOCTYPE html>` + `</html>` present
- CSS: confirm last char is `}` (no truncation)

### Browser API gotchas
- This site is opened via `file://`. Some APIs (service workers, install prompts) only work over HTTPS or localhost. PWA tasks MUST degrade gracefully when SW registration fails — wrap in try/catch, log to console, don't break the page.

### Git staging
- Commits land in parent `ClaudeProjects` repo (alex-workout has no own git).
- Always `git add <specific-file>` from inside `alex-workout/`. Never `-A` or `.`.

---

## Iteration discoveries

(Ralph: append new findings below as you go.)

### TASK-01 (manifest.json)
- Validation loop `for f in *.js; do ...done` fails in sandbox due to "Unhandled node type: string" — run `node --check tracker.js` directly instead, then verify HTML with grep -l.
- All 8 HTML files have identical `<head>` structure ending with `<link rel="stylesheet" href="style.css">` — manifest link goes immediately after.
- CSS last char is `}` (+ newline), `tail -c 2 | xxd` shows `7d 0a` — valid.

### TASK-02 (barbell SVGs)
- icon-192.svg: viewBox="0 0 192 192" — bar centered at y=90 (h=12), 2 plates per side.
- icon-512.svg: viewBox="0 0 512 512" — all coords scaled by 512/192 (≈2.667) from 192 version.
- Symmetry check: center of inner plate pair = half of total width in both files. Bar center = half height.
- Transparent background by default in SVG (no explicit `background` needed on the root element).

### TASK-03 (service-worker.js)
- Cache name `alex-workout-v1`, lists all 13 static assets explicitly.
- Fetch handler skips non-GET by returning early (no `respondWith`), then cache-first with network fallback and dynamic cache insertion.
- `node --check` validates service worker syntax fine (no DOM APIs used at parse time).

### TASK-04 (SW registration in all HTML pages)
- All 8 HTML files share the same footer pattern `</footer>\n</body>\n</html>` — inserted script block just before `</body>` in each.
- `progress.html` already had `<script src="tracker.js"></script>` as the last script — inserted SW registration after it.
- Pattern: `if ('serviceWorker' in navigator)` guard + try/catch + `.then/.catch` for console logging.
- Validation shortcut: `grep -l "serviceWorker.register" *.html | wc -l` → must be 8.

### TASK-06 (JSON Import)
- Import button triggers a hidden `<input type="file" accept="application/json">` via `.click()` in the button handler.
- FileReader + JSON.parse; validate array shape + required keys before showing confirm dialog.
- De-dup by `id`: build a Set of existing ids, filter imported entries to only those not in the set, concat and save.
- `importFileInput.value = ''` reset after import so the same file can be re-imported if needed.
- `importBtn` and `importFileInput` guarded with null-check in case `progress.html` structure changes.

### TASK-07 (chart-mode toggle)
- Three buttons (Weight/Volume/Est. 1RM) inserted above `.chart-container` in a `.chart-mode-group` flex div.
- Active state managed via `.active` class; initialized on page load from `localStorage.getItem('chart-mode')` (default 'weight').
- Button IDs follow pattern `chart-mode-{mode}` where mode is 'weight', 'volume', or '1rm'.
- `updateChart()` reads mode from localStorage each call — no global state needed.
- Volume y-axis uses `padL = 70` (wider than default 50) and `.toFixed(0)` to prevent label overflow.
- `·` in "kg·reps" is the literal Unicode middle dot — works fine in a JS string literal.
- Added initial `updateChart()` call in `initTracker()` so the canvas shows the placeholder text on first load.

### TASK-08 (Weekly Volume card)
- `renderWeeklyVolume()` added to tracker.js; renders a 4-row table into `#weekly-volume` div.
- Uses `Date.now() - 7*24*60*60*1000` for 7-day cutoff; volume = weight × reps × sets.
- Called on initial render, after form submit, after clear, and after import JSON.
- Exposed globally via `window.renderWeeklyVolume`.
- No new CSS needed — existing `table/th/td` rules supply correct dark styling.
- Section inserted in progress.html between "Log Entry" and "Progress Chart" sections.

### TASK-09 (PR detection)
- `addEntry` filters `log` by `entry.exercise`, reduces to max `weight` (default 0 if no prior entries).
- New entry gets `is_pr = true` only when `entry.weight > prevBest` (strict greater-than, not >=).
- `is_pr` is an optional field — older entries that lack it load fine; no schema migration needed.
- No UI changes in this task; TASK-10 handles the toast notification.

### TASK-10 (PR toast notification)
- `addEntry` now returns the new entry object — allows caller to inspect `is_pr` without re-reading localStorage.
- `showToast(message)` creates a `<div class="toast">`, appends to body, waits 4000ms, adds `.fade-out` class (CSS `opacity: 0; transition: opacity 0.5s`), then removes on `transitionend` (uses `{ once: true }` listener).
- Toast positioned `fixed; bottom: 1.5rem; right: 1.5rem` so it never blocks the form.
- `pointer-events: none` on `.toast` so it doesn't block clicks on underlying elements.
- The `×` reps symbol is written as `\xD7` (Unicode multiplication sign) inside a template literal to avoid a raw non-ASCII character in the JS source.
- Toast CSS appended at end of style.css after the chart-mode block.

### TASK-11 (Rest timer on push.html)
- Timer placed as `.rest-timer` div inside `.container`, before the Exercises `<section>`.
- Inline IIFE script immediately after the markup (before exercises section) — avoids polluting global scope.
- Start button toggles to "Pause" while running; Reset always resets remaining to the input value.
- Web Audio API: create `AudioContext`, connect `OscillatorNode → GainNode → destination`, `osc.start()` + `osc.stop(currentTime + 0.3)`, close context in `onended`. Whole call wrapped in try/catch — fails silently if audio API unavailable.
- `input.change` handler only syncs `remaining` when not running (avoids mid-session disruption).
- CSS: `.rest-timer`, `.rest-timer-controls`, `.rest-display` added at end of style.css after toast block.
- `.rest-display` font-size: 3rem with `var(--accent)` color matches the gold accent system.

### TASK-12 (Shared rest-timer fragment)
- `rest-timer.html` is a full valid HTML file (DOCTYPE + html/body tags) so it passes the `*.html` validation loop.
- Fetch+inject uses `DOMParser` to parse the fetched HTML, then moves `doc.body.childNodes` into the mount div via `document.adoptNode`.
- Scripts from innerHTML/adoptNode don't auto-execute — must query `.querySelectorAll('script')` in the mount, create new `<script>` elements with the same `.textContent`, and call `replaceChild` to force execution.
- Fetch is wrapped in try/catch; `.catch()` is a no-op — both paths ensure graceful degradation on `file://` where fetch is blocked.
- Mount div `<div id="rest-timer-mount">` placed inside `.container` after the hero, before the first `<section>`.
- In `abs.html` the first section is "Schedule" (not "Exercises") — that's the correct insertion point.

### TASK-13 (Plate calculator)
- Greedy algorithm uses `Math.floor(Math.round(remaining / plate * 1000) / 1000)` to avoid floating-point drift when dividing.
- Remaining is tracked with `Math.round(x * 1000) / 1000` after each plate deduction to keep values clean.
- "Bar only" edge case: show friendly message when no plates are needed rather than empty output.
- `plates.html` added to Quick Links in index.html; nav on plates.html includes self-link with `.active` class.
- service-worker.js was NOT updated to cache plates.html — its explicit asset list now lags behind. Update TASK-03 cache list when touching the SW.
- Validation confirmed: `<!DOCTYPE html>` + `</html>` present; CSS ends `7d 0a`; `tracker.js` syntax clean.

### TASK-14 (Streak banner on index.html)
- Banner div `<div id="streak-banner" class="streak-banner">` placed after `.hero` div, before first `<section>`.
- Script uses `localDate(d)` helper (getFullYear/getMonth/getDate) for local-timezone dates — avoids UTC midnight drift vs `toISOString().slice(0,10)`.
- Week workouts: compute Monday offset (`dow === 0 ? -6 : 1 - dow`), loop 7 days, check Set of workout days.
- Streak: starts from today if worked out, else yesterday, else 0. Walks backward while Set has that date.
- `.streak-banner` CSS: centered, `font-size: 0.85rem`, `color: var(--text-dim)`, `padding: 0.5rem 0 1.5rem`.
- When log is empty, banner shows "0 workouts this week · 0 day streak".

### TASK-15 (Print styles)
- `@media print` block appended at end of style.css after `.streak-banner`.
- Hides `nav` and `footer` with `display: none`.
- Forces `body { background: #fff !important; color: #000 !important; font-size: 12pt; }`.
- `.container` gets `max-width: 100%; padding: 0` so content fills the full print width.
- `.phase-card` and `table` get `page-break-inside: avoid` to prevent mid-card/mid-table page breaks.
- CSS last char remains `}` + newline (`7d 0a`) — validation still passes.

### TASK-16 (Responsive mobile styles + table-wrap)
- Expanded existing `@media (max-width: 600px)` to `@media (max-width: 700px)` — wider breakpoint catches more tablet-sized viewports.
- Added `.nav-links a { font-size: 0.7rem; }` inside the mobile block (base is 0.8rem).
- Added `.table-wrap { overflow-x: auto; }` as a utility class in the base styles (not inside media query) — works at all sizes but only activates when content overflows.
- Wrapped all `<table>` elements in HTML files with `<div class="table-wrap">`. Files: index.html (2 tables), abs.html, references.html, recovery.html (2 tables), plates.html (2 tables).
- Table inside `.protocol-card` in recovery.html still wrapped — inner div indentation kept consistent with sibling elements.

### TASK-17 (Keyboard shortcuts)
- Single `keydown` listener added inside `initTracker()`, attached to `document`.
- Guard: `if (e.target.tagName === 'TEXTAREA') return` — prevents firing when typing in a textarea (future-proof; no textarea exists in the form currently).
- Esc: iterates `['weight-input','reps-input','sets-input','notes-input']` and sets `.value = ''` on each (null-checked with getElementById).
- Ctrl+E / Cmd+E: `e.preventDefault()` then `exportBtn.click()` — reuses the existing export handler without duplicating logic. `exportBtn` is already in scope from the `initTracker` closure.
- No changes to `progress.html` needed — handler is entirely in `tracker.js`.

### TASK-05 (Install App button)
- `beforeinstallprompt` only fires on HTTPS/localhost; on `file://` it never fires — button stays `display:none`, which is the correct graceful degradation.
- Button placed inside `.hero` div in `index.html`, after the subtitle `<p>`.
- `.install-btn` CSS class only sets `display: none` and `margin`; the existing global `button` rule supplies gold/dark styling (no duplication needed).
- `appinstalled` event hides the button after install (covers the auto-install path without a click).
- Added second `<script>` block in index.html after the SW registration script — keeps concerns separate.
