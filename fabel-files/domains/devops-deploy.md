# Domain: DevOps & Deployment

Applies when: shipping code to environments — CI/CD, containers, config, environment variables, releases, rollbacks, platform services (Vercel/Railway/AWS/etc.). Load with `CLAUDE-FABEL.md`.

## 1. Failure modes

- **Trusting the green checkmark.** The pipeline says deployed; nobody verifies the running artifact contains the change. Auto-deploy hooks fail silently, caches serve stale builds, and the old version keeps running while everyone debugs the new code that isn't there.
- **Config drift.** Dev, staging, and prod diverge quietly — an env var set by hand months ago, a config edited over SSH — until behavior differs and nobody knows why.
- **No rollback plan.** Discovering during the incident that the previous version can't be restored (migration already ran, artifact overwritten, nobody knows the last good tag).
- **Snowflake surgery.** Fixing prod by hand instead of through code/config, creating a server whose state exists nowhere but itself.
- **Localhost assumptions.** Code that assumes a writable disk, a persistent filesystem, one instance, or a local timezone — all false on most platforms (containers restart, filesystems are ephemeral, replicas race).
- **Secrets in the pipeline.** Tokens committed, echoed into build logs, or baked into images.

## 2. Standards

- **Every deploy is verified by a fingerprint probe**: a version string, build hash, or sentinel change observable from outside (a header, an endpoint, a grep on served JS). "The pipeline succeeded" is never the evidence; "the running system serves my fingerprint" is.
- **Rollback is defined BEFORE deploying**: the exact command/click that restores the previous version, and confirmation that migrations shipped alongside don't make it impossible (see `database.md`, expand/contract).
- All environment changes travel through code/config in version control. A hand-applied fix is a temporary incident action that must be codified the same day.
- Every env var the app reads is documented (name, purpose, where it's set per environment) and validated at startup — the app fails loudly at boot with the missing name, not at 2am at first use.
- Images/builds are reproducible: pinned base images and dependencies; the artifact tested is the artifact shipped.
- Logs from the platform are reachable and readable BEFORE you need them; a service isn't "deployed" until you've seen its runtime logs once.
- Nothing depends on local disk persisting, a single instance running, or the container's clock/timezone.

## 3. Defaults

- Boring first: platform-native buildpacks/presets over custom Dockerfiles; managed services over self-hosted; one process per container.
- Env-specific behavior keys off ONE explicit variable (`APP_ENV`), not clever inference from hostnames.
- Health checks that verify real readiness (can serve, dependencies reachable), not just process-up.
- Deploy checklist order: config/secrets in place → migrate (expand phase) → deploy → fingerprint probe → watch logs/errors for the first minutes → contract later.

## 4. Verification

- Probe the fingerprint on the live environment and QUOTE it. For web: curl the version endpoint or grep the sentinel in a served asset. Never conclude "deployed" from the dashboard alone.
- Exercise the changed behavior itself in the deployed environment, not just the homepage.
- Read startup logs after deploy: clean boot, no config warnings, no crash-restart loop (a service that restarts every 30s shows green on most dashboards).
- After env-var changes: verify from INSIDE the runtime (log the presence — never the value — of required vars at boot).
- Rollback rehearsal for consequential releases: actually restore the previous version once and probe it.

## 5. Edge cases that always matter

- The gap between build time and runtime: env vars available at one but not the other (framework-dependent, a classic).
- Caches at every layer: build cache, CDN, browser, package registry — each can serve you the past; each needs its own invalidation move.
- Cold starts and concurrency: the first request after idle; two instances handling what the code assumed was one.
- Serverless termination: the platform freezes/kills instances after the response — fire-and-forget async work dies silently; await it or queue it.
- Time: containers on UTC while cron and humans aren't; certificate and token expiry as a scheduled outage.

## 6. Stop signals

- "Works locally, fails deployed" → run the deployment-issue checklist mechanically (env vars → config → cache → artifact → versions, per `protocols/debugging.md` §7.3) BEFORE reading more application code. It's on that list far more often than not.
- You're about to edit anything by hand on a server/dashboard as the fix → do it only as incident response, and codify it immediately after.
- The deploy requires perfectly-timed manual steps to avoid an outage → redesign to additive steps; humans don't hit timing windows.
- You can't answer "how do I roll this back?" in one sentence → not ready to deploy.
