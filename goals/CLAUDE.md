# Goals

Personal goal/habit tracker. Next.js 16 + Prisma 5 + PostgreSQL.

**Method: Ralph (ghuntley/how-to-ralph-wiggum). HEADLESS BUILD MODE.**

## Running
- Dev: `npm run dev` (requires DATABASE_URL + ADMIN_PASSWORD in `.env`)
- The DB may NOT be running during ralph iterations. Do NOT depend on it for verification.

## Validation
TypeScript-only verification. Lint and DB are out of scope for ralph runs.

```bash
npx tsc --noEmit
```

This must pass with zero errors after every task.

## Architecture
- `src/app/page.tsx` — public read-only goal view (client component, fetches `/api/goals`)
- `src/app/dashboard/page.tsx` — private daily checklist + notes (client component)
- `src/app/login/page.tsx` — bcrypt password login
- `src/app/api/goals/route.ts` — list goals
- `src/app/api/habits/[date]/route.ts` — habits + logs for a given date
- `src/app/api/notes/route.ts` — notes CRUD
- `src/app/api/auth/{login,logout}/route.ts` — session cookies
- `src/lib/auth.ts` — bcrypt + session cookie helpers
- `src/lib/db.ts` — Prisma client singleton
- `src/middleware.ts` — auth gate for /dashboard
- `prisma/schema.prisma` — Goal, Habit, HabitLog, Note models
- `src/generated/prisma/` — generated Prisma client (do NOT edit)

## Agent Rules (Headless)
- HEADLESS BUILD MODE. NO plan mode. NO clarifying questions. NO `AskUserQuestion`.
- One task per session. Verify with `npx tsc --noEmit`. Commit. Exit.
- Stage explicitly by path (`git add goals/<file>`). NEVER `git add -A` or `git add .` — the parent ClaudeProjects repo has peer sessions.
- Commit message: `feat(TASK-XX): description` or `refactor(TASK-XX): ...` or `fix(TASK-XX): ...`.
- After each task: append discoveries to `AGENTS.md`.
- If stuck: prefix the task line with `BLOCKED:` in IMPLEMENTATION_PLAN.md and move on.
- NO `npm install`. NO new dependencies. Use what's already in `package.json`.
- NO migrations. NO seed runs. DB might be down.
- Match existing styling: Tailwind 4 utility classes already in use, no styled-components, no css-in-js.
- React 19 + Next.js 16 App Router. Default to client components only when needed (`'use client'`); server components otherwise.
- Do NOT edit `src/generated/prisma/` — it's auto-generated.
- Commits land in parent `ClaudeProjects` repo (goals has no own remote).
