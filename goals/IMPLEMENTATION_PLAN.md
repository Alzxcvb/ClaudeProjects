# Goals — Implementation Plan

Headless ralph loop builds these one at a time. Pick the first `- [ ]` with all `Depends:` satisfied. Mark complete with `- [x]` after verify+commit. If a task gets stuck, prefix the task line with `BLOCKED:` (the keyword on its own list-item line) and move on.

---

## Phase 1 — Type & component extraction

- [x] **TASK-01**: Create `src/types/index.ts` exporting four interfaces: `Goal`, `Habit`, `HabitLog`, `Note`. Pull the canonical shapes from the inline interfaces currently duplicated in `src/app/page.tsx` and `src/app/dashboard/page.tsx`. Resolve discrepancies by taking the SUPERSET of fields (e.g. if one file has `value?: number` and the other doesn't, include it). Do NOT import from this file yet — TASK-02 and TASK-03 will.

- [x] **TASK-02**: Refactor `src/app/page.tsx` to import `Goal`, `Habit`, `HabitLog`, `Note` from `src/types/index.ts` and remove the inline duplicates. Verify `npx tsc --noEmit` still passes — no behavior change.
  Depends: TASK-01

- [ ] **TASK-03**: Refactor `src/app/dashboard/page.tsx` to import shared types from `src/types/index.ts` and remove inline duplicates. Verify `npx tsc --noEmit` still passes — no behavior change.
  Depends: TASK-01

- [ ] **TASK-04**: Create `src/components/Skeleton.tsx` — a client component (`'use client'` not needed if no state) that renders animated placeholder bars. Props: `lines?: number` (default 3), `className?: string`. Use Tailwind `animate-pulse bg-gray-200 dark:bg-gray-700 rounded h-4`.

- [ ] **TASK-05**: Create `src/components/EmptyState.tsx` — a presentational component. Props: `title: string`, `description?: string`, `icon?: string` (emoji), `action?: ReactNode`. Centers content with Tailwind, gray-500 text. Used as fallback when collections are empty.

---

## Phase 2 — UI polish

- [ ] **TASK-06**: Update `src/app/layout.tsx` `metadata` export with proper `title: "Goals — Personal Tracker"`, `description: "Daily habits, notes, and milestones across active and on-deck goals."`, and `themeColor: "#000000"`. Add `viewport` export with `width: 'device-width', initialScale: 1`.

- [ ] **TASK-07**: Replace any `alert()` calls in `src/app/dashboard/page.tsx` with an inline error banner (a div with `role="alert"`, Tailwind red styling, dismissable via state). If no `alert()` calls exist, prefix this task with `BLOCKED:` (no-op). The banner state should clear automatically after 4 seconds.

- [ ] **TASK-08**: Use `Skeleton` from TASK-04 in `src/app/dashboard/page.tsx` while the initial habits/goals fetch is loading (replace any current "Loading…" text). Show 5 skeleton lines.
  Depends: TASK-04

- [ ] **TASK-09**: Use `EmptyState` from TASK-05 in `src/app/page.tsx` when the goals fetch returns an empty array. Title "No active goals", description "Add goals from the dashboard to see them here.", icon "🎯".
  Depends: TASK-05

---

## Phase 3 — Features

- [ ] **TASK-10**: Add a date-jump `<input type="date">` near the day-nav on `src/app/dashboard/page.tsx`. When changed, navigate the dashboard to show that date's habits (use the existing date-state pattern, whatever it is). Don't break existing prev/next-day navigation.

- [ ] **TASK-11**: Add a "Today" button next to the date-jump that resets the dashboard's date to today's `YYYY-MM-DD`. Disabled when already on today.
  Depends: TASK-10

- [ ] **TASK-12**: Add keyboard shortcuts to `src/app/dashboard/page.tsx`: ArrowLeft = previous day, ArrowRight = next day, `T` key = today. Attach via `addEventListener('keydown')` in a useEffect with proper cleanup. Skip the handler when `event.target` is an input/textarea/select.
  Depends: TASK-11

- [ ] **TASK-13**: Add a JSON Export button on `src/app/dashboard/page.tsx`. On click, builds a `Blob` from `{ exportedAt, date, goals, habitsForDate, notes }` (using whatever client-side state already exists) and triggers a download as `goals-YYYY-MM-DD.json`. Pure client-side, no API call.

- [ ] **TASK-14**: Add a `@media print` block to `src/app/globals.css`: hide nav and buttons (`nav, button { display: none !important; }`), force light background, single-column body, page-break-inside avoid for habit list items.

- [ ] **TASK-15**: Add a today-indicator visual cue on dashboard's date display — when the displayed date equals today's `YYYY-MM-DD`, render with a green dot or "Today" pill next to the date.
  Depends: TASK-10

---

## Phase 4 — Quality & DX

- [ ] **TASK-16**: Create `src/lib/api.ts` exporting a typed `apiFetch<T>(url: string, init?: RequestInit): Promise<T>` helper. On non-2xx, throws an Error with the response status text. JSON parses the body. Used as a foundation — no callers updated in this task.

- [ ] **TASK-17**: Refactor `seed.js` to use ESM imports (`import` instead of `require`). The file uses `require('@prisma/client')` and similar. Convert to `import { PrismaClient } from '@prisma/client'`. Add `"type": "module"` to package.json ONLY if needed — otherwise rename to `seed.mjs` (and update `npm run seed` script accordingly). Goal: clear the `@typescript-eslint/no-require-imports` error.

- [ ] **TASK-18**: Add JSDoc comments to every exported function in `src/lib/auth.ts` and `src/lib/db.ts`. One- or two-line `/** ... */` describing what the function does and its return shape. Don't change function bodies.
