# Domains — per-specialty standards files

Each file in this folder is a standards module for one domain. The core manual (`../CLAUDE-FABEL.md`) governs HOW to work in any domain; a domain file adds the judgment that is specific to one — the traps, the bar, the pre-made decisions, and what verification concretely means there.

## The assignment model

These are designed so you can build **specialists**: assign one domain file to one weaker model and it becomes "the data-pipeline model" or "the frontend model." Load order for a specialist:

1. `CLAUDE-FABEL.md` (always — process is universal)
2. Exactly ONE `domains/<x>.md` (its specialty)
3. Protocols from `../protocols/` on trigger, as the core manual directs

Loading multiple domain files into one weak model dilutes the effect; the point of a specialist is a small, deep rule set it can actually hold. A task spanning two domains (e.g., an API + its DB migration) is a task for two specialists in sequence, or one specialist plus the coach checking the boundary.

## The shared skeleton

Every domain file has the same six sections, so specialists are trained/prompted uniformly and the coach can grade uniformly:

1. **Failure modes** — the traps weak models fall into in THIS domain (extends `protocols/failure-modes.md`)
2. **Standards** — the bar; what "good" means here, stated checkably
3. **Defaults** — decisions pre-made so the model doesn't burn judgment on them; deviate only with a written one-line reason
4. **Verification** — what "watch it work" concretely means in this domain
5. **Edge cases that always matter** — the domain's recurring gotchas, checked every time
6. **Stop signals** — domain-specific tripwires that mean "step back, the approach is wrong"

## The catalog

| File | Specialty |
|---|---|
| `web-frontend.md` | UI: React/Next, components, styling, accessibility |
| `web-backend.md` | HTTP APIs, services, auth, request handling |
| `data-pipeline.md` | ETL, ingestion, transforms, batch jobs |
| `database.md` | Schema design, migrations, SQL, indexing |
| `cli-tools.md` | Command-line tools and their UX contract |
| `automation-scripting.md` | Scripts, cron jobs, scrapers, browser automation |
| `llm-apps.md` | LLM-powered features: prompts, agents, RAG, evals |
| `security-review.md` | Secure coding and defensive code review |
| `devops-deploy.md` | CI/CD, containers, environments, releases |
| `testing-strategy.md` | Test design: what to test, how, and what not to |
| `data-analysis.md` | Statistics, exploratory analysis, honest reporting |
| `technical-writing.md` | Docs, READMEs, runbooks, written reports |
| `mobile-apps.md` | Native/React Native mobile development |
