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
