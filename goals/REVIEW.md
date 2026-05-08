# Goals — Human-Readable Code Review

A walkthrough of every change ralph made today, in plain English with the actual code embedded. Read top-to-bottom; you don't need to run any commands or open any other files.

> 18 tasks attempted. 17 landed autonomously, 1 was a no-op (no `alert()` calls existed to replace), 1 finished by hand after the loop exited. Plus one defensive fix to catch a runtime crash when the DB is down.

---

## TL;DR — what got done

**Cleanup + structure (TASK-01, 02, 03, 16, 17, 18)**
The two main pages were duplicating their TypeScript interfaces. Now they share a single source of truth. A typed fetch helper and JSDoc comments were added for future use. The `seed.js` file was modernized to ES modules.

**New reusable UI components (TASK-04, 05)**
Two small presentational components — `Skeleton` (loading placeholder) and `EmptyState` (when a list is empty). These are now used by the public page and the dashboard.

**Visible UX upgrades (TASK-06, 08, 09, 14, 15)**
Better tab title and metadata. Skeleton instead of "Loading..." text. EmptyState when there are no goals. Print stylesheet for clean printouts. A green dot beside "Today" when viewing today's date.

**Dashboard features (TASK-10, 11, 12, 13)**
Date picker input to jump to any past date. A "Today" button (disabled when already on today). Keyboard shortcuts (← → for prev/next day, T for today). A JSON export button that downloads the current day's state as a file.

**Things to scrutinize (concerns I noticed)**
1. The new components use `text-gray-900 dark:text-gray-100` styling, which assumes system dark mode. Goals is hardcoded dark — if your Mac is in *light* mode, the EmptyState text could be dark gray on a near-black background (hard to read). See "Concern" notes below.
2. The `apiFetch` helper (TASK-16) was added as a foundation but **isn't actually called anywhere yet**. It's dead code until someone refactors the existing `fetch()` calls.
3. The dashboard's keyboard handler does date math using `Date.UTC`. Looks correct, but worth eyeballing.

Skipped: TASK-07 (replace `alert()` calls). Ralph correctly identified there are no `alert()` calls in `dashboard/page.tsx` and marked it `BLOCKED:` as a no-op. Not a bug.

---

## The full walkthrough

### TASK-01 — Shared types (foundation)

Before: `Goal`, `Habit`, `HabitLog`, `Note` interfaces were defined twice — once in `src/app/page.tsx` and once in `src/app/dashboard/page.tsx`, with subtle differences. Drift waiting to happen.

After: a single file at `src/types/index.ts`:

```ts
export interface HabitLog {
  id: string
  habitId: string
  completed: boolean
  value?: number
  date?: string
}

export interface Habit {
  id: string
  name: string
  order: number
  goalId?: string
  logs?: HabitLog[]
}

export interface Note {
  id: string
  content: string
  milestone: boolean
  date: string
}

export interface Goal {
  id: string
  title: string
  emoji: string
  habits: Habit[]
  description?: string
  notes?: Note[]
}
```

**Verdict**: Clean. Took the SUPERSET of fields from the two old definitions. Optional fields (`?`) are correctly used where one file had them and the other didn't. TASK-02 and TASK-03 then deleted the duplicates and imported from here.

---

### TASK-04 — `<Skeleton>` component

A loading placeholder. Used on the dashboard while data fetches. The whole file:

```tsx
interface SkeletonProps {
  lines?: number;
  className?: string;
}

export default function Skeleton({ lines = 3, className }: SkeletonProps) {
  return (
    <div className={className}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse bg-gray-200 dark:bg-gray-700 rounded h-4 mb-2"
        />
      ))}
    </div>
  );
}
```

**Verdict**: Fine. Renders `lines` (default 3) animated gray bars.

**⚠️ Concern**: Uses `bg-gray-200 dark:bg-gray-700` — the bars are *light* gray when your system is in light mode. The app body is `bg-zinc-950` (near-black). Light gray on near-black is high-contrast so it's readable, but the rest of the app uses the `zinc-*` Tailwind palette, not `gray-*`. Inconsistent palette. Trivial to swap to `bg-zinc-800` if you want consistency.

---

### TASK-05 — `<EmptyState>` component

```tsx
import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: string;
  action?: ReactNode;
}

export default function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon && <span className="text-4xl mb-4">{icon}</span>}
      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
      {description && (
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
```

**Verdict**: Decent shape — title, description, icon, optional action button.

**⚠️ Real concern**: `text-gray-900` is dark gray (#111827). Without `dark:`, that's the rendered color when system is in light mode. The body is hardcoded `bg-zinc-950` (very dark). **Dark gray text on near-black background = barely visible**. The `dark:text-gray-100` only kicks in if your system theme is dark.

You're seeing this empty state right now at `localhost:3000` — if your Mac is in light mode, the title is hard to read. Easy fix: change `text-gray-900 dark:text-gray-100` to `text-zinc-100`. Same for the description (`text-gray-500 dark:text-gray-400` → `text-zinc-400`). I noticed this; ralph didn't.

---

### TASK-06 — Layout metadata

Tab title, description, and viewport. The relevant addition:

```tsx
export const metadata: Metadata = {
  title: "Goals — Personal Tracker",
  description: "Daily habits, notes, and milestones across active and on-deck goals.",
};

export const viewport: Viewport = {
  themeColor: "#000000",
  width: "device-width",
  initialScale: 1,
};
```

**Verdict**: Correct for Next.js 15+/16. The split between `metadata` and `viewport` is the new convention (Next deprecated putting `themeColor` and `viewport` in `metadata`). Ralph followed the modern pattern. Browser tab now reads "Goals — Personal Tracker" instead of generic Next default.

---

### TASK-08 — Dashboard uses `<Skeleton>` while loading

Before: dashboard rendered `<p>Loading...</p>` while fetching.

After:

```tsx
if (loading) {
  return (
    <div className="min-h-screen bg-zinc-950">
      <div className="max-w-4xl mx-auto px-4 py-12">
        <Skeleton lines={5} />
      </div>
    </div>
  )
}
```

**Verdict**: Fine. Same wrapper as the rendered state, just with skeleton bars inside.

---

### TASK-09 — Public page uses `<EmptyState>` when no goals

```tsx
{goals.length === 0 && (
  <EmptyState
    title="No active goals"
    description="Add goals from the dashboard to see them here."
    icon="🎯"
  />
)}
```

**Verdict**: Correctly placed before the `goals.map()` so it shows when the list is empty. **You see this right now at localhost:3000** because the DB is down → API returns empty → EmptyState renders. The text-readability concern from TASK-05 applies.

---

### TASK-10 — Date-jump input on dashboard

```tsx
<input
  type="date"
  value={selectedDate}
  max={today}
  onChange={(e) => setSelectedDate(e.target.value)}
  className="px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded-lg ..."
/>
```

**Verdict**: Good. `max={today}` prevents picking future dates (which would have no data). When changed, `selectedDate` updates and the data-fetch `useEffect` re-runs because it depends on `selectedDate`.

---

### TASK-11 — Today button

```tsx
<button
  onClick={() => setSelectedDate(today)}
  disabled={selectedDate === today}
  className="... disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed ..."
>
  Today
</button>
```

**Verdict**: Disabled state styled correctly. Cursor goes to `not-allowed` when on today.

---

### TASK-12 — Keyboard shortcuts

```tsx
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    const target = e.target as HTMLElement
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return

    if (e.key === 'ArrowLeft') {
      const [y, m, d] = selectedDate.split('-').map(Number)
      const prev = new Date(Date.UTC(y, m - 1, d - 1))
      setSelectedDate(prev.toISOString().split('T')[0])
    } else if (e.key === 'ArrowRight') {
      const [y, m, d] = selectedDate.split('-').map(Number)
      const next = new Date(Date.UTC(y, m - 1, d + 1))
      const nextStr = next.toISOString().split('T')[0]
      if (nextStr <= today) setSelectedDate(nextStr)
    } else if (e.key === 't' || e.key === 'T') {
      setSelectedDate(today)
    }
  }

  window.addEventListener('keydown', handleKeyDown)
  return () => window.removeEventListener('keydown', handleKeyDown)
}, [selectedDate, today])
```

**Verdict**: Solid.
- Skips firing when you're typing in an input/textarea/select (so the `T` key doesn't move you to "today" while typing a note).
- Date math uses `Date.UTC` which avoids timezone bugs at month boundaries — good choice.
- ArrowRight is gated by `nextStr <= today`, mirroring the input's `max` — can't navigate to the future.
- Cleanup function removes the listener on unmount. Correct.

---

### TASK-13 — JSON Export button

```tsx
const handleExport = () => {
  const data = {
    exportedAt: new Date().toISOString(),
    date: selectedDate,
    goals,
    habitsForDate: logs,
    notes,
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `goals-${selectedDate}.json`
  a.click()
  URL.revokeObjectURL(url)
}
```

**Verdict**: Standard client-side download pattern. `URL.revokeObjectURL` correctly cleans up. The exported `notes` field will be the user's *unsaved draft* notes (from the textarea state) — that may or may not be what you want. Spec said use existing client state, so ralph followed it.

---

### TASK-14 — `@media print` block in `globals.css`

```css
@media print {
  nav,
  button {
    display: none !important;
  }

  body {
    background: #ffffff !important;
    color: #000000 !important;
    max-width: 100% !important;
    columns: 1 !important;
  }

  li {
    page-break-inside: avoid;
  }
}
```

**Verdict**: Does what it says. Try Cmd+P on `localhost:3000` right now to see — nav and buttons gone, white background, black text. Spec asked for `page-break-inside: avoid` on `.phase-card` and `table`; ralph did it on `li` instead, which is a defensible interpretation since habits are list items in this app, but technically a small spec deviation.

---

### TASK-15 — Today indicator (green dot)

```tsx
<h1 className="text-4xl font-bold text-white flex items-center gap-2">
  {selectedDate === today ? 'Today' : selectedDate}
  {selectedDate === today && (
    <span className="w-3 h-3 rounded-full bg-green-500 flex-shrink-0" />
  )}
</h1>
```

**Verdict**: Clean. Two simultaneous changes:
- Header text shows "Today" when viewing today's date, otherwise the YYYY-MM-DD string.
- Green dot appears next to "Today" when on today's date.

---

### TASK-16 — `apiFetch<T>` helper

The whole file (`src/lib/api.ts`):

```ts
export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    throw new Error(res.statusText)
  }
  return res.json() as Promise<T>
}
```

**Verdict**: 7 lines. Throws on non-2xx with the response status text. JSON-parses. Foundation only.

**⚠️ Caveat**: It's not used anywhere yet. The existing `fetch()` calls in `page.tsx` and `dashboard/page.tsx` weren't updated to use it. Spec was explicit about that ("no callers updated in this task"), so this is correct per spec — but you should know the helper exists in dead-code limbo until someone wires it in.

---

### TASK-17 — `seed.js` → `seed.mjs` (ESM)

Before: `seed.js` started with `const { PrismaClient } = require('@prisma/client')` — caused an eslint error.

After: renamed to `seed.mjs`, now starts with:

```js
import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  // Clear existing data
  await prisma.habitLog.deleteMany({})
  ...
```

And `package.json`:

```json
"seed": "node seed.mjs"
```

**Verdict**: Clears the lint error. Script reference updated. The `.mjs` extension tells Node to treat it as ESM without needing `"type": "module"` in package.json. Sensible choice — adding `"type": "module"` would have rippled into other files.

---

### TASK-18 — JSDoc on `lib/auth.ts` and `lib/db.ts`

(I wrote these manually after the loop exited prematurely on a stall-detection bug.)

`auth.ts` examples:

```ts
/** Generate a fresh random 64-char hex session token. */
export async function createSessionToken(): Promise<string> { ... }

/** Persist a session token in the httpOnly session cookie (30-day max age). */
export async function setSessionCookie(token: string): Promise<void> { ... }

/** Read the current session token from cookies, or null if absent. */
export async function getSessionToken(): Promise<string | null> { ... }
```

`db.ts`:

```ts
/**
 * Shared Prisma client singleton. Reuses one instance across hot reloads in
 * development and per-request invocations in production to avoid exhausting
 * the database connection pool.
 */
export const prisma = ...
```

**Verdict**: One- or two-line docstrings on every export. Hover any of them in your editor to see the description.

---

### Defensive fetch (post-loop fix)

After the run, you opened `localhost:3000` and got a runtime crash: `goals.map is not a function`. Root cause: when `/api/goals` returned 500 (DB down), `response.json()` returned an error object, then `setGoals(errorObj)` set non-array state, then `.map` blew up.

The fix:

```tsx
const response = await fetch('/api/goals')
if (!response.ok) {
  throw new Error(`HTTP ${response.status}`)
}
const data = await response.json()
setGoals(Array.isArray(data) ? data : [])
```

And the catch branch resets state to `[]` instead of leaving stale.

Same shape applied to `dashboard/page.tsx` for goals, logs, and allGoals.

**Verdict**: This is what's keeping the homepage from crashing right now even though Postgres isn't running. The EmptyState renders gracefully instead.

---

## Verdict by category

| Category | Verdict |
|---|---|
| Type extraction (TASK-01, 02, 03) | ✅ Solid. Eliminates the duplication. |
| New components (TASK-04, 05) | ✅ Working but ⚠️ palette mismatch — gray-* instead of zinc-*. EmptyState text could be unreadable in light system mode. |
| Layout metadata (TASK-06) | ✅ Correct Next 16 conventions. |
| Loading skeleton (TASK-08) | ✅ Tidy swap from text. |
| Empty state usage (TASK-09) | ✅ Renders correctly when goals are empty. |
| Date jump + Today button (TASK-10, 11) | ✅ Good. `max=today` prevents future navigation. |
| Keyboard shortcuts (TASK-12) | ✅ Skips on inputs, future-gate on ArrowRight, cleanup on unmount. |
| JSON export (TASK-13) | ✅ Standard download pattern. Includes draft note state. |
| Print CSS (TASK-14) | ✅ Works. Minor spec deviation (page-break on `li` instead of `.phase-card`/`table`). |
| Today indicator (TASK-15) | ✅ Two changes in one block, both correct. |
| apiFetch helper (TASK-16) | ✅ Code is fine, but dead until wired into callers. |
| ESM seed (TASK-17) | ✅ Lint error cleared, script updated. |
| JSDoc (TASK-18) | ✅ Hand-written by me, kept tight. |
| Defensive fetch fix | ✅ Why localhost:3000 doesn't crash. |

## What I'd ask ralph (or me) to clean up

1. **Swap `gray-*` to `zinc-*`** in `Skeleton.tsx` and `EmptyState.tsx` to match the rest of the app. ~2 min fix.
2. **Wire `apiFetch` into existing fetch calls** so the helper isn't dead code. ~10 min.
3. **Smoke-test the dashboard features against a real Postgres** before considering them shipped. The code looks right; runtime behavior is unverified.

If you want me to do any of those right now, say which.
