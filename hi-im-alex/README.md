# Hi, I'm Alex — hiimalex.ai

One-page marketing site for "Hi, I'm Alex" Consulting (Wyoming LLC). Replaces the Carrd draft at `himalex.carrd.co`.

## Stack
Plain static HTML + inline CSS. No build step. Deploy anywhere.

## Local preview
```
open index.html
```
Or: `python3 -m http.server 8000` then visit http://localhost:8000

## Deploy options (pick one)
- **Vercel** (recommended): `vercel --prod` from this folder. Add `hiimalex.ai` in the dashboard and update nameservers at your registrar.
- **Netlify**: drag & drop the folder, or `netlify deploy --prod`.
- **GitHub Pages**: push to a repo, enable Pages on `main` / root.
- **Cloudflare Pages**: connect the repo, auto-deploys on push.

## Placeholders to fill in before launch
- `YOUR-CALENDLY-HANDLE` → real Calendly URL
- `YOUR-X-HANDLE` → X/Twitter handle
- `YOUR-LINKEDIN` → LinkedIn vanity URL
- `alex@hiimalex.ai` → real inbox (Google Workspace or forwarder)

## Structure
Single `index.html` file with 6 sections: hero, services, proof (brand pillars), testimonials, booking CTA, footer. Mobile responsive at 720px breakpoint. Dark theme with warm orange accent.

## Next steps (per business plan Day 1–7)
- [ ] Fill placeholders above
- [ ] Set up Google Workspace or email forwarder on hiimalex.ai
- [ ] Set up Calendly with "Claude Quick Start Session" (90 min, Stripe connected)
- [ ] Deploy to Vercel + point hiimalex.ai at it
- [ ] Add real testimonials as they arrive (replace `.quote.placeholder` blocks)
