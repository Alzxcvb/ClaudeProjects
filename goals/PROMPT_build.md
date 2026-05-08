# Build Mode Prompt — Goals

You are in HEADLESS BUILD MODE for Goals (Next.js 16 + Prisma 5). No clarifying questions. No plan mode. Implement → verify → commit → exit.

## Your Task
Pick ONE incomplete task from `IMPLEMENTATION_PLAN.md`, implement it, verify it, mark it complete, commit, exit.

## Process
1. Read `IMPLEMENTATION_PLAN.md` — find the FIRST `- [ ]` task with all `Depends:` satisfied.
2. Read `CLAUDE.md` for project conventions.
3. Read `AGENTS.md` for accumulated knowledge.
4. Read referenced existing files before editing.
5. Implement the task. Edit existing files where it fits; create new files only when the task says so.
6. **Verify**: `npx tsc --noEmit` — must exit 0 with no errors.
7. Update `IMPLEMENTATION_PLAN.md` — change `- [ ]` to `- [x]` for that task.
8. Update `AGENTS.md` — append new discoveries.
9. Stage explicitly: `git add <every-file-touched>`. NEVER `git add -A` or `git add .`.
10. Verify staged scope: `git diff --cached --stat`. Unstage anything unexpected.
11. Commit: `git commit -m "feat(TASK-XX): short description"` (or `refactor`/`fix`).
12. Exit.

## Task Selection Rules
Pick the FIRST incomplete task that:
- Is `- [ ]` (not `- [x]`, not prefixed with `BLOCKED:`)
- Has all `Depends:` tasks already `- [x]`

If no eligible task exists, exit immediately.

## Validation
```bash
npx tsc --noEmit
```
Exit 0 = pass. Any TypeScript error = fail. Re-edit and retry until clean before committing.

## If Stuck
- Prefix the task line with `BLOCKED: <one-line reason>` and move to the next eligible task.
- Do NOT exit unless ALL eligible tasks are blocked or done.

## Hard Rules
- One task per session.
- NO `npm install`. NO new dependencies.
- NO migrations. NO seed runs. NO `npm run dev`. The DB might be down.
- Plain Tailwind utility classes; match existing UI.
- React 19 / Next.js 16 App Router conventions: server components by default, `'use client'` only when needed.
- Don't edit `src/generated/prisma/` — it's auto-generated.
- Stage by path. Never `git add -A` or `git add .`.
- localStorage / cookies / Web APIs only — no new SDK pulls.

## Spec-Code Discrepancy
If existing code disagrees with the task description in a way that would change user-visible behavior: prefix with `BLOCKED:` and move on.
