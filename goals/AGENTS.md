# AGENTS.md — Goals

Discoveries and conventions accumulated across iterations. Append, don't rewrite.

---

## Initial knowledge (seeded 2026-05-08)

### Verification command
- ONLY `npx tsc --noEmit` — must pass after every task.
- Skipping eslint deliberately: project has 1 pre-existing error (seed.js require) and 7 unused-var warnings. A lint-fix task is in the plan; before that lands, lint is unreliable as a gate.

### Type duplication problem
- `src/app/page.tsx` and `src/app/dashboard/page.tsx` BOTH define inline `interface Goal`, `Habit`, `HabitLog`, `Note`. They drift. The plan extracts these to `src/types/index.ts` early — once that's done, all new code should import from there.

### Tailwind / styling
- Tailwind v4 via `@tailwindcss/postcss`. Utility classes throughout. No styled-components. No CSS modules in use yet (globals.css holds project-level styles).

### Routing
- Next.js 16 App Router. `src/middleware.ts` gates `/dashboard/*` behind auth.
- Public route: `/` (read-only goal view).
- API routes use Web `Request`/`Response`, not the older NextApiRequest.

### Prisma client
- Generated at `src/generated/prisma/` — DO NOT edit, but you CAN read its types if needed.
- `src/lib/db.ts` exports a singleton `prisma`.

### Auth
- bcryptjs hashes the password against `ADMIN_PASSWORD` env. Session is a signed cookie (see `src/lib/auth.ts`).

### Git staging
- Commits land in parent `ClaudeProjects` repo. Always `git add goals/<file>` from inside `goals/`. Never `-A` or `.`.

---

## Iteration discoveries

(Ralph: append new findings below as you go.)

## TASK-01 (2026-05-08)
- Created `src/types/index.ts` with superset `Goal`, `Habit`, `HabitLog`, `Note` interfaces.
- Key discrepancies resolved: `HabitLog.date` optional (present in page.tsx, absent in dashboard); `Habit.goalId` optional (present in dashboard, absent in page.tsx); `Habit.logs` optional (present in page.tsx, absent in dashboard); `Goal.description` and `Goal.notes` optional (present in page.tsx, absent in dashboard).
- No callers updated yet — TASK-02 and TASK-03 will import from here.

## TASK-02 (2026-05-08)
- Removed 4 inline interfaces from `src/app/page.tsx`; replaced with `import type { Goal, HabitLog } from '@/types'`.
- `Habit` and `Note` not needed as explicit annotations — accessed via `Goal.habits` and `Goal.notes`.
- `@/*` alias resolves to `./src/*` (confirmed in tsconfig.json).
- Optional field guard: `habit.logs ?? []` for `getStreak`/`getCompletionRate` calls; `goal.notes?.length` and `goal.notes?.map(...)` for render guard.
- `npx tsc --noEmit` passes clean (exit 0).

## TASK-03 (2026-05-08)
- Removed inline `HabitLog`, `Habit`, `Goal` interfaces from `src/app/dashboard/page.tsx`; replaced with `import type { Goal, Habit, HabitLog } from '@/types'`.
- `GoalWithNote` kept as a local interface — it's not a duplicate of any shared type (subset of `Goal` used for the all-goals dropdown state).
- Shared `Habit.goalId` is optional vs. the old local `goalId: string` (required). No runtime impact — `goalId` is never accessed in the dashboard JSX, only `habit.id` and `habit.name`.
- `npx tsc --noEmit` passes clean (exit 0).

## TASK-04 (2026-05-08)
- Created `src/components/Skeleton.tsx` — no `'use client'` needed (pure presentational, no state or hooks).
- `src/components/` directory did not previously exist; this is the first component file.
- `Array.from({ length: lines })` used for indexed rendering without a range utility.
- `npx tsc --noEmit` passes clean (exit 0).

## TASK-05 (2026-05-08)
- Created `src/components/EmptyState.tsx` — pure presentational, no state/hooks, no `'use client'`.
- `ReactNode` imported as `import type { ReactNode } from 'react'` — type-only import sufficient for TSC.
- `npx tsc --noEmit` passes clean (exit 0).

## TASK-06 (2026-05-08)
- Updated metadata in `src/app/layout.tsx` with descriptive title and description.
- `themeColor` belongs in the `Viewport` export (not `Metadata`) in Next.js 14+/16 — the `Metadata` type does not include `themeColor`. Both `Viewport` and `Metadata` types imported from `"next"`.
- `viewport` export includes `themeColor: "#000000"`, `width: "device-width"`, `initialScale: 1`.
- `npx tsc --noEmit` passes clean (exit 0).

## TASK-07 (2026-05-08)
- BLOCKED: No `alert()` calls found anywhere in `src/app/dashboard/page.tsx`. Task is a no-op.

## TASK-08 (2026-05-08)
- Replaced the centered "Loading..." paragraph with `<Skeleton lines={5} />` inside a layout-matching wrapper (`min-h-screen bg-zinc-950`, `max-w-4xl mx-auto px-4 py-12`).
- Imported `Skeleton` from `@/components/Skeleton` — default export, no destructuring needed.
- `npx tsc --noEmit` passes clean (exit 0).

## TASK-09 (2026-05-08)
- Imported `EmptyState` from `@/components/EmptyState` in `src/app/page.tsx`.
- Rendered `<EmptyState>` conditionally when `goals.length === 0`, placed inside the existing `space-y-8` div before the `goals.map(...)` call.
- No need to change the map — it naturally produces nothing for an empty array; the EmptyState sits above as the visible fallback.
- `npx tsc --noEmit` passes clean (exit 0).

## TASK-11 (2026-05-08)
- Added "Today" button inline with the date input, after it in the flex row.
- `disabled={selectedDate === today}` uses the existing `today` constant — no new state needed.
- Disabled styling: `disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed` matches existing button patterns.
- `npx tsc --noEmit` passes clean (exit 0).

## TASK-12 (2026-05-08)
- Added `keydown` useEffect after the fetch useEffect in `src/app/dashboard/page.tsx`.
- Handler skips when `event.target.tagName` is INPUT, TEXTAREA, or SELECT — prevents nav triggering while typing in habit value inputs or note textareas.
- ArrowLeft/ArrowRight use `Date.UTC(y, m-1, d±1)` + `.toISOString().split('T')[0]` to avoid local-timezone off-by-one errors.
- ArrowRight blocked by `nextStr <= today` guard (same boundary as the date input's `max={today}`).
- useEffect depends on `[selectedDate, today]` — re-registers on date change so handler always closes over the current value.
- `npx tsc --noEmit` passes clean (exit 0).

## TASK-13 (2026-05-08)
- Added `handleExport` to `src/app/dashboard/page.tsx` — builds JSON blob from `{ exportedAt, date, goals, habitsForDate: logs, notes }` and triggers download as `goals-YYYY-MM-DD.json`.
- Pattern: create `<a>` element, set `href` + `download`, `.click()`, then `URL.revokeObjectURL` — no DOM side effects left behind.
- `notes` state is the draft-note input map (`Record<string, string>`), not persisted notes. That's the only notes-like state available client-side; acceptable per task spec ("using whatever client-side state already exists").
- Export JSON button placed in header between "Manage Goals" and "Logout".
- `npx tsc --noEmit` passes clean (exit 0).

## TASK-14 (2026-05-08)
- Added `@media print` block to `src/app/globals.css`.
- Hides `nav` and `button` elements; forces `body` to white background + black text; sets `li { page-break-inside: avoid }` for habit list items.
- CSS-only change — no TypeScript involved; `npx tsc --noEmit` passes trivially (exit 0).

## TASK-10 (2026-05-08)
- Added `selectedDate` state (mutable, initialized to today) separate from the fixed `today` constant.
- Kept `today` as an immutable reference for comparison (used in TASK-11/15 for "Today" pill logic).
- Changed `useEffect` dependency from `[today]` to `[selectedDate]`; added `setLoading(true)` at fetch start so skeleton shows on date change.
- Updated all API calls (`/api/habits/${selectedDate}`, note `date: selectedDate`) to use `selectedDate`.
- Date input placed inline with h1 in a flex row; h1 shows "Today" when `selectedDate === today`, otherwise shows the date string.
- `max={today}` prevents selecting future dates.
- `npx tsc --noEmit` passes clean (exit 0).
