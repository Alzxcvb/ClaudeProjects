# Goals — Personal Goal Tracking

A full-stack web app for tracking daily habits, notes, and milestones across 5 active goals + 5 on-deck goals.

**Stack:** Next.js 16 + Prisma 5 + PostgreSQL on Railway

## Features

- **Public page** — Read-only view of active goals with habit streaks, completion rates, and recent notes
- **Private dashboard** — Daily habit checklist + notes/milestones editor (password-protected)
- **Goal management** — Activate/archive on-deck goals, reorder active goals
- **Habit tracking** — Checkbox completion + optional numeric values (sleep hours, pages read, tokens, etc.)
- **Streaks** — Current streak counter + 7-day completion rate per habit
- **Notes & milestones** — Tag notes as milestones with date tracking

## Setup

### Local Development

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Set up database** (requires Prisma Postgres or local PostgreSQL)
   ```bash
   DATABASE_URL="..." npx prisma migrate deploy
   ```

3. **Generate Prisma client**
   ```bash
   npx prisma generate
   ```

4. **Seed initial data** (optional, when DB is running)
   ```bash
   npm run seed
   ```

5. **Start dev server**
   ```bash
   npm run dev
   ```

6. **Login** — Set `ADMIN_PASSWORD` env var as bcrypt hash
   ```bash
   # Use bcryptjs to generate hash, then set in .env:
   ADMIN_PASSWORD="$2a$10$..."
   ```

### Environment Variables

```env
# Database
DATABASE_URL="postgresql://user:password@host/goals"

# Auth
ADMIN_PASSWORD="bcrypt-hashed-password"
SESSION_SECRET="random-string-for-session-signing"

# Deployment
NODE_ENV="production"
```

## Deployment to Railway

1. **Create Railway project** and connect GitHub repo
2. **Set environment variables** in Railway dashboard:
   - `DATABASE_URL` (PostgreSQL plugin auto-creates this)
   - `ADMIN_PASSWORD` (bcrypt hash of login password)
   - `SESSION_SECRET` (random string)
   - `NODE_ENV=production`

3. **Configure startCommand** — `railway.toml` runs migrations and seed:
   ```toml
   [deploy]
   startCommand = "npx prisma migrate deploy && npm start"
   ```

4. **Seed database** (run once after first deploy):
   ```bash
   railway run npm run seed
   ```

## Pages & Routes

| Path | Auth | Purpose |
|---|---|---|
| `/` | None | Public goal overview + streaks |
| `/login` | None | Password login |
| `/dashboard` | Required | Today's habit checklist + notes |
| `/dashboard/goals` | Required | Manage goals (activate, reorder) |
| `/api/goals` | GET: None / POST/PUT/DELETE: Required | Goal CRUD |
| `/api/habits/[date]` | GET: None / POST: Required | Habit logs by date |
| `/api/notes` | GET: None / POST: Required | Notes CRUD |
| `/api/auth/login` | None | Password verification → session cookie |
| `/api/auth/logout` | Required | Clear session |

## Database Schema

**Goals**
- `id` (String, CUID)
- `title`, `description`, `emoji`
- `status` (ACTIVE / ON_DECK / ARCHIVED)
- `order` (for UI sorting)
- `createdAt` (DateTime)

**Habits**
- `id`, `goalId` (FK)
- `name`, `order`

**HabitLogs**
- `id`, `habitId` (FK), `date` (ISO string)
- `completed` (Boolean), `value` (Float, optional)
- Unique constraint: `(habitId, date)`

**Notes**
- `id`, `goalId` (FK)
- `content`, `milestone` (Boolean), `date`
- `createdAt` (DateTime)

## Default Goals & Habits

### Active
1. **Master Claude & Engineering** 🤖
   - AI Tokens (OpenRouter)
   - Project Work

2. **Health & Habits** 🥗
   - Clean Meals
   - Sleep Hours

3. **Fitness** 💪
   - Workout
   - Activity

4. **Style & Attitude** ✨
   - Outfit Intention
   - Journaling

5. **Read, Write & Build Audience** 📚
   - Pages Read
   - Substack Posts
   - Social Posts

### On Deck
- Martial Arts 🥋
- Diving & Australia Reef 🤿
- Grad School / NZ Citizenship / NS Fellowship 🎓
- Israeli Citizenship 🇮🇱
- Personal Book Writing ✍️

## Known Issues

- Seeding requires active database connection; may need to run manually on Railway
- Middleware uses deprecated Next.js convention (works fine, suppress warning if desired)

## Next Steps

- Deploy to Railway
- Test login flow with bcrypt password
- Run seed script on deployed database
- Share public URL with team
