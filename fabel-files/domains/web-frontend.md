# Domain: Web Frontend

Applies when: building or changing UI — components, pages, styling, client-side state. Load with `CLAUDE-FABEL.md`; the core manual still governs process.

## 1. Failure modes

- **The three missing states.** Building only the data-loaded happy path. Every view that fetches has FOUR states: loading, error, empty, loaded. Weak models ship one.
- **Div soup.** Non-semantic markup (`div` + `onClick` instead of `button`), which silently breaks keyboards, screen readers, and forms.
- **State duplication.** Copying server data into local state "to edit it," creating two sources of truth that drift. Also: putting state in a global store because it was annoying to pass down twice.
- **useEffect as duct tape.** Effects that synchronize state to other state, fire twice, or re-implement what the framework's data layer already does. Most effects in weak-model code shouldn't exist.
- **One-viewport styling.** Layouts verified only at the width the dev server happened to open at, in light mode only.
- **Hydration blindness.** Server/client markup mismatch (dates, random IDs, `window` access during render) producing warnings that get ignored.

## 2. Standards

- Every fetch-backed view handles loading / error / empty / loaded, and the error state says something a user can act on.
- Interactive elements are the semantic element (`button`, `a`, `label`, `form` with submit) — reachable and operable by keyboard alone.
- One source of truth per piece of data. Server state lives in the data-fetching layer; local state is for genuinely local things (open/closed, draft input).
- No console errors or warnings in the changed flow. A warning you didn't explain is a surprise (core manual §1).
- Works at 360px and 1440px widths, and in both light and dark themes if the app has them.
- Images have dimensions or aspect ratios (no layout shift); lists have stable keys (never the array index when items reorder).

## 3. Defaults

- Follow the framework's grain: file conventions, data-fetching idiom, and router of the existing codebase — never introduce a parallel pattern.
- State placement: start local to the component; lift only when a second consumer exists; global store only for genuinely app-wide concerns (session, theme).
- Derive, don't sync: compute derived values during render instead of mirroring them into state with effects.
- Styling: whatever system the codebase already uses. No new CSS approach in a task that isn't about CSS.
- Reuse the codebase's existing components before writing new ones — grep for an existing `Button`/`Modal`/`EmptyState` first.

## 4. Verification

- Load the real page and CLICK THE ACTUAL FLOW. Rendering without interacting verifies almost nothing.
- Open the browser console during the flow; zero new errors/warnings.
- Force each of the four states: throttle or block the network for loading/error, use an account/filter with no data for empty.
- Tab through the changed UI with the keyboard once.
- Resize to phone width; toggle dark mode if it exists.

## 5. Edge cases that always matter

- Text: very long unbroken strings, empty strings, unicode/emoji, user-generated HTML (must be escaped).
- Lists: 0 items, 1 item, 1000 items (does it virtualize or at least not freeze?).
- Timing: double-click on submit (double-fire?), navigating away mid-request, stale response arriving after a newer one.
- Auth: what does this view do logged out, or when the session expires mid-use?
- Locale: dates and numbers rendered for a non-US locale; RTL if the app claims to support it.

## 6. Stop signals

- You are fighting the framework (suppressing its warnings, working around its router or data layer) → your approach is against the grain; find the idiomatic path.
- A component needs more than ~5 props to configure its variants → it's two components.
- You're adding an effect to fix an effect → delete both and re-derive the data flow.
- The fix is `!important`, a z-index arms race, or a hardcoded pixel nudge → the layout model is wrong one level up.
