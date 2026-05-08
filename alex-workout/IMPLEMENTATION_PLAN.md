# Alex Workout — Implementation Plan

Headless ralph loop builds these one at a time. Pick the first `- [ ]` with all `Depends:` satisfied. Mark complete with `- [x]` after verify+commit. If blocked, prefix with `BLOCKED:`.

---

## Phase 1 — PWA (offline + installable)

- [x] **TASK-01**: Create `manifest.json` with `name` "Alex Workout", `short_name` "Workout", `start_url` ".", `display` "standalone", `theme_color` "#c9a227", `background_color` "#000", and an `icons` array referencing `icon-192.svg` (192×192, type `image/svg+xml`) and `icon-512.svg` (512×512). Link the manifest from EVERY HTML page (`<link rel="manifest" href="manifest.json">`).

- [x] **TASK-02**: Create `icon-192.svg` and `icon-512.svg` — simple barbell glyph (a horizontal bar with two plates on each side), color `#c9a227` on transparent background. Hand-write the SVG, no external assets. Both files should have proper `viewBox` matching their dimensions.
  Depends: TASK-01

- [x] **TASK-03**: Create `service-worker.js` that on `install` caches all current static assets (every `*.html`, `style.css`, `tracker.js`, `manifest.json`, both icon SVGs) under cache name `alex-workout-v1`, and on `fetch` serves cache-first with network fallback. Skip caching for non-GET requests.
  Depends: TASK-02

- [x] **TASK-04**: Register the service worker in EVERY HTML page via inline `<script>` near `</body>`. Wrap in `if ('serviceWorker' in navigator)` AND a try/catch so it never throws on `file://`. Log success or failure to console. Use `navigator.serviceWorker.register('service-worker.js')`.
  Depends: TASK-03

- [x] **TASK-05**: Add an "Install App" button on `index.html` that listens for `beforeinstallprompt`, captures the event, shows the button when available, hides after install or user dismiss. Style with existing CSS variables.
  Depends: TASK-04

---

## Phase 2 — Tracker upgrades

- [x] **TASK-06**: Add a JSON Import button next to the existing Export button on `progress.html`. On click, opens a file picker (`<input type="file" accept="application/json">`), validates that parsed value is an array and every item has `id, timestamp, session, exercise, weight, reps, sets`. Merge with existing log (de-duplicate by `id` — existing entries win). Save to localStorage. Show a `confirm()` dialog before merge: "Import N entries from file?".

- [x] **TASK-07**: Add a chart-mode toggle on `progress.html` above the canvas — three buttons in a button group: "Weight", "Volume", "Est. 1RM". Update `updateChart()` in `tracker.js` to plot the selected metric: weight = `e.weight`; volume = `e.weight * e.reps * e.sets`; 1RM = `e.weight * (1 + e.reps/30)` (Epley formula). Default to "Weight". Persist selection in localStorage key `chart-mode`. Adjust the y-axis label format ("kg", "kg·reps", "kg") accordingly.
  Depends: TASK-06

- [x] **TASK-08**: Add a "Weekly Volume" summary card on `progress.html` (above the chart, below the log form). Compute total volume per session category (push/pull/legs/abs) for the last 7 days from localStorage entries. Render as a 4-row table with columns: Session, Total Volume (kg), Entries.
  Depends: TASK-07

- [x] **TASK-09**: Add PR detection in `tracker.js`. When `addEntry` is called, check if the new entry's weight is the highest ever logged for that exercise. If so, set `entry.is_pr = true` before saving. Don't break loading of older entries that lack `is_pr`. Don't change rendering yet — TASK-10 handles UI.
  Depends: TASK-08

- [x] **TASK-10**: Add a toast notification system to `tracker.js` + `style.css`. When `is_pr` is set on a newly added entry, show a toast "🏆 New PR — {exercise}: {weight}kg × {reps}" for 4 seconds, fades out. Bottom-right corner. Use yellow accent `#c9a227`. Pure DOM (no library).
  Depends: TASK-09

---

## Phase 3 — Gym utilities

- [x] **TASK-11**: Add a rest timer section at the TOP of `push.html` (under the nav, above the exercises). Markup: input for seconds (default 90, min 10, max 600), Start button, Reset button, big countdown display "MM:SS". On Start, count down. On done, play a 440 Hz sine wave for 0.3 seconds via Web Audio API (no external file). Inline `<script>` is fine.

- [x] **TASK-12**: Extract the rest-timer markup + script from TASK-11 into a single shared file `rest-timer.html` (HTML fragment + inline `<script>`) and load it via a small fetch+inject snippet at the top of `pull.html`, `legs.html`, `abs.html`. Replace the inline timer in `push.html` with the same fetch+inject. The fetch must degrade gracefully on `file://` (try/catch; if fetch fails, just skip).
  Depends: TASK-11

- [x] **TASK-13**: Create `plates.html` — plate calculator. Inputs: target total weight (kg), bar weight (kg, default 20). Output: list of plates per side, e.g. "Per side: 20 + 10 + 5 + 2.5 (= 37.5 kg)". Use a greedy algorithm with available plates [25, 20, 15, 10, 5, 2.5, 1.25] kg. Style with existing CSS. Add it to the Quick Links table on `index.html`.

- [x] **TASK-14**: Add a streak banner to `index.html` — a small `<div>` under the hero section. Reads localStorage key `alex-workout-log`, computes (a) workouts logged this calendar week (Mon–Sun) by unique `YYYY-MM-DD` from `timestamp`, (b) current consecutive-day streak ending today or yesterday. Render: "X workouts this week · Y day streak". Inline `<script>`.

- [x] **TASK-15**: Add a `@media print` block to `style.css`. Hide `nav` and `footer` (`display: none`). Force black on white (`body { background: #fff !important; color: #000 !important; }`). Single column. Larger body font (`12pt`). `page-break-inside: avoid;` for `.phase-card` and `table`.

---

## Phase 4 — Polish

- [ ] **TASK-16**: Add a `@media (max-width: 700px)` block to `style.css`. Nav becomes vertical stack with reduced font; tables get `overflow-x: auto` wrapper class `.table-wrap`; `.container` padding reduces; hero `h1` shrinks to `1.8rem`; nav links smaller. Apply `.table-wrap` to all `<table>` parents in HTML where horizontal scroll on small screens is needed.

- [ ] **TASK-17**: Add keyboard shortcuts to `progress.html` via `tracker.js`. Esc clears all log-form inputs (weight, reps, sets, notes). Ctrl+E (or Cmd+E) triggers the existing export. Don't break existing handlers; attach with `addEventListener` and respect `event.target` (don't trigger when typing in textarea).
  Depends: TASK-10

- [ ] **TASK-18**: Add a "Duplicate last entry" button on the log form in `progress.html`. When clicked: if an exercise is selected, pre-fill weight, reps, sets, notes from the most recent entry for that exercise. If no prior entry, button stays disabled. Reuses `getExerciseHistory()` in `tracker.js`.
  Depends: TASK-17
