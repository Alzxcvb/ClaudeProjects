# Domain: Mobile Apps (React Native / Expo and native)

Applies when: building or changing mobile applications — screens, navigation, device APIs, offline behavior, store delivery. Load with `CLAUDE-FABEL.md`.

The defining property: the app runs on hardware you don't control, on networks that vanish, under an OS that kills it whenever it likes — and shipping fixes takes days of review, not a redeploy. The bar for "verified" is higher here because the cost of wrong is higher.

## 1. Failure modes

- **Simulator-only confidence.** Everything verified on the simulator's fast CPU, perfect network, and mouse input. Real devices bring notches, slow radios, fat fingers, permission dialogs, and memory pressure — where mobile bugs actually live.
- **Online-only design.** Every screen assumes a network. In an elevator the app becomes a spinner museum; worse, a mid-request drop corrupts state.
- **Lifecycle amnesia.** Ignoring that the OS backgrounds and KILLS the app routinely. Draft input, navigation state, and in-flight operations evaporate; the user returns to a reset app and blames it correctly.
- **Permission optimism.** Code paths that assume camera/location/notifications were granted. Denial isn't an edge case on mobile; it's a common user choice, and the "denied" path is usually unbuilt.
- **One-device layouts.** Pixel-perfect on the dev's phone; broken on small screens, notches/safe areas, large system font sizes, and Android's back button.
- **Keyboard blindness.** Inputs covered by the keyboard, no way to dismiss it, forms unusable one-handed.

## 2. Standards

- Every network-touching screen handles the four states (loading/error/empty/loaded) PLUS offline — and errors offer retry, not dead ends.
- State survives death: user input worth more than a few seconds of work persists (draft storage) and restores after the OS kills the app. Test by actually killing it.
- Every permission has a designed denial path: the feature degrades or explains, never crashes or silently no-ops; permission requested at the moment of need with context, not at launch.
- Mutations that can fire during flaky connectivity are idempotent or queued — a tapped button and a network drop must not double-charge or half-save.
- Layout uses safe areas, works at the largest accessibility font, and touch targets meet platform minimums (~44pt). Android back button behaves sanely on every screen.
- Secrets and tokens in the platform keystore/keychain, never in async storage or bundled code (the bundle is downloadable and readable — treat it as public).
- Follow each platform's conventions where they diverge (navigation patterns, share sheets, haptics); a platform-wrong app feels broken even when it works.

## 3. Defaults

- Expo managed workflow until a concrete need forces ejecting/native modules — and CHECK Expo's support surface before concluding it can't do something (it usually can).
- The stack the project already has: its navigation library, its state approach, its styling. No parallel patterns.
- Server state via a fetch/cache library with offline-aware retries; local state minimal and persisted deliberately.
- Lists virtualized by default (`FlatList`/equivalent); images sized and cached; animations on the native driver.
- OTA updates (where used) for JS-only fixes; store releases planned around review latency — never assume a same-day fix is possible.

## 4. Verification

- **On-device beats simulator** — at minimum, the changed flow runs once on real hardware (or the honest statement that it couldn't, per core-manual calibration). Simulator-only verification is labeled as such in the report.
- The kill test: background the app → kill it from the switcher → relaunch. Is state where the user left it?
- The airplane test: enable airplane mode mid-flow; observe designed behavior (queue/retry/message), then restore and confirm recovery.
- The permission test: deny each permission the flow touches; walk the denial path.
- Layout sweep: smallest supported device size, largest system font, both orientations if supported; keyboard open on every form.
- Watch the metrics while driving the flow once: memory climbing (leak) or jank on scroll — catch it now, not in reviews.

## 5. Edge cases that always matter

- Interruptions mid-flow: incoming call, notification tap-away, app switcher — then return. Where does the user land?
- Slow radios: 3G-class throttling on first load; timeouts that make sense for cellular, not office wifi.
- Storage full, low battery mode (background work throttled), and the OS revoking permissions between launches ("allow once").
- Deep links and push-notification taps arriving when the app is cold, backgrounded, or already on that screen — three different code paths.
- Old app versions in the wild talking to new APIs (mobile clients CANNOT be force-upgraded; the API must tolerate stragglers — see `web-backend.md` on additive evolution).

## 6. Stop signals

- Fighting the framework's navigation or gesture system with manual overrides → wrong pattern for the platform; find the idiomatic one.
- A feature needs a native module in a managed Expo app → checkpoint decision (ejecting is expensive and one-way for the project) — verify support first, surface the tradeoff, don't drift into it.
- The screen needs three nested scroll views or absolute-positioned pixel nudges → the layout model is wrong one level up.
- You're persisting more and more state to patch restore bugs one by one → define the app's lifecycle/state model once instead of whack-a-mole.
