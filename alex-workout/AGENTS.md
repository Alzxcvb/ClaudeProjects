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

### TASK-05 (Install App button)
- `beforeinstallprompt` only fires on HTTPS/localhost; on `file://` it never fires — button stays `display:none`, which is the correct graceful degradation.
- Button placed inside `.hero` div in `index.html`, after the subtitle `<p>`.
- `.install-btn` CSS class only sets `display: none` and `margin`; the existing global `button` rule supplies gold/dark styling (no duplication needed).
- `appinstalled` event hides the button after install (covers the auto-install path without a click).
- Added second `<script>` block in index.html after the SW registration script — keeps concerns separate.
