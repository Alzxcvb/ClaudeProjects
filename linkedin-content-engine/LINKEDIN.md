# Posting to LinkedIn from the CRM

Two tracks. Posting is buildable today and needs no LinkedIn review. Analytics
is gated behind an application that cannot be submitted yet.

**The queue, as of 19 August 2026.** The swipe file has been imported, so the
library is 164 variants across 156 active ideas. Running every gate over all of
them:

| | count |
|---|---|
| ready to post right now | **131** |
| blocked, inside the 90 day cooldown | 17 |
| blocked, tagged for an image | 6 |
| blocked, over the 3,000 character limit | 7 |
| blocked, no body recorded | 3 |

Version one publishes **text only**. Attaching a visual needs a separate upload
step to obtain a `urn:li:image`, which is not built, so the publisher refuses an
image tagged variant rather than silently dropping the picture. Seven variants
are simply too long, the largest being 22,642 characters after escaping against
a 3,000 limit. Those need editing, not code.

Everything below was checked against LinkedIn's own documentation on
2026-08-18. Where the docs are silent, it says so instead of guessing.

---

## What Alex has to do (about 10 minutes, all in a browser)

Run `./li setup` to get this same list with your current state filled in.

1. **Confirm you are a super admin** of `linkedin.com/company/hiimalex-llc`.
   A page is required to create an app, and a super admin has to verify it.
   The verification link expires 30 days after it is issued.

2. **Create the app** at `linkedin.com/developers/apps/new`
   - App name: `Hi I'm Alex Content Engine`
   - LinkedIn Page: `hiimalex-llc`
   - Then Settings tab, click Verify, finish the page verification.

3. **Products tab, request both.** Both are self serve. Neither needs a review.
   - `Share on LinkedIn`
   - `Sign In with LinkedIn using OpenID Connect`

   The second one is not optional. It is the only self serve way to learn your
   own member id, and that id is required as the post author. Without it the
   posting call has nothing to put in the `author` field.

4. **Get a token. Two ways, and the quick one needs nothing deployed.**

   A note on why the scripted path uses your own domain rather than
   `localhost`: LinkedIn's docs contradict each other on this. The canonical
   OAuth page says the redirect URL must be HTTPS, while their own sample
   application page tells you to register `http://localhost:8080/login`. Their
   loopback flow is documented only for native PKCE, which is not self serve
   and has to be enabled by a LinkedIn contact. Rather than gamble your one
   setup attempt on an unresolved contradiction, the callback goes on
   hiimalex.ai, which satisfies the strictest reading.

   **Quick path, recommended for the first token.** LinkedIn ships a token
   generator that needs no redirect URL and no callback page at all:
   ```
   https://www.linkedin.com/developers/tools/oauth/token-generator
   ```
   Pick the app, tick `openid`, `profile` and `w_member_social`, generate,
   copy the token, then:
   ```
   ./li token
   ```

   **Scripted path, better for the monthly renewal.** This one needs the
   callback page live, because LinkedIn requires an HTTPS redirect URL.
   On the Auth tab add exactly:
   ```
   https://www.hiimalex.ai/li/callback
   ```
   Register the apex form as a second entry too, so either host works:
   ```
   https://hiimalex.ai/li/callback
   ```
   It must match exactly and cannot contain a `#`. The www form is the default
   because the apex answers with a 307 to www, and while a browser follows that,
   LinkedIn matches the registered string exactly.

   **Both pages are already deployed and verified live** (HTTP 200). Then put the Client ID and Secret in `.li-app.json` here:
   ```json
   {"client_id": "...", "client_secret": "...",
    "redirect_uri": "https://www.hiimalex.ai/li/callback"}
   ```
   That file is gitignored. Do not paste the secret into a chat window.
   Then run `./li auth`.

5. **Either way, finish with:**
   ```
   ./li probe               asks LinkedIn which endpoint the app may call
   ./li preview <variant>   shows exactly what would be sent, sends nothing
   ```

---

## Definition of done: current state

| # | Item | State |
|---|---|---|
| 1 | App created, page verified, OAuth done, token stored | **Needs Alex.** The code is built, and tested against a fake LinkedIn. Nothing has touched the real API. Steps above. |
| 2 | One real test post published, URN captured | **Needs step 1.** `./li post` does publish and record as one operation. |
| 3 | Which endpoint is the app entitled to call | **Answered from the docs.** Nothing has touched real LinkedIn yet; `./li probe` confirms it live once a token exists. See below. |
| 4 | Token expiry recorded, renewal reminder scheduled | **Reminder scheduled** (installed in cron, verified with `crontab -l`). The expiry **date** cannot exist until there is a token, so that half follows step 1. |
| 5 | Community Management application submitted | **Blocked, and the blocker is real.** See below. |

---

## 3. Which posting endpoint

**Answer: use `/rest/posts`. Fall back to `/v2/ugcPosts` only if the probe says otherwise.**

The handoff called this genuinely ambiguous, and it was, but the Posts API
documentation settles it. Its permissions table lists:

| Permission | Description |
|---|---|
| `w_member_social` | Post, comment, and like posts on behalf of an authenticated member. |

So `w_member_social` is documented as a valid permission for `/rest/posts`.
The same page also states the Posts API replaces the ugcPosts API. Required
headers are `Linkedin-Version: 202606` and `X-Restli-Protocol-Version: 2.0.0`.
Version `202508` sunset on 2026-08-17, so anything at or after `202606` is safe.

This is documented entitlement, not yet a live confirmation, because confirming
it needs a token. `./li probe` closes that gap without publishing anything: it
POSTs an empty JSON body to each endpoint and reads the status code. An empty
body cannot create a post, but it still has to clear authorization first, so

- `403` means the app is not permitted to call that endpoint
- `400` means it got past permission and is complaining about the body, which
  is what entitlement looks like
- `401` means the token is bad and the probe proves nothing

The full report is written to `liapi/endpoint-probe-report.json`.

### The escaping trap, which matters more than the endpoint choice

`/rest/posts` does not accept plain text. Its `commentary` field is in
LinkedIn's "little" format, and the rule is absolute:

> All reserved characters need to be escaped with a backslash, even if those
> characters are not used in one of the supported elements or templates.

Reserved: `|` `{` `}` `@` `[` `]` `(` `)` `<` `>` `#` `\` `*` `_` `~`

**Six of the variants already in `content.db` contain these characters.**
Sending them raw means LinkedIn tries to parse them as mention or hashtag
syntax and the copy comes out mangled, live, under Alex's real name.
`liapi/littletext.py` handles this, with one deliberate exception: a `#`
followed by word characters is left alone so real hashtags stay clickable.
`./li preview` shows the escaped form before anything is sent.

`/v2/ugcPosts` uses plain text and needs no escaping, which is why escaping is
applied per endpoint and never globally.

**Watch URLs in particular.** The grammar reserves `(`, `)` and `_` regardless
of context, so a link like `wikipedia.org/wiki/Some_Article (worth a read)`
goes out as `Some\_Article \(worth a read\)`. That is what LinkedIn's spec
asks for, but whether it affects link preview generation is not documented and
has not been tested live. `./li preview` prints the exact outgoing text, so
check any post containing a URL with brackets or underscores before sending
the first one.

---

## 4. Token expiry

Access tokens last **60 days**. There is no programmatic refresh: LinkedIn
issues true refresh tokens only to approved Marketing Developer Platform
partners. Renewal means running `./li auth` again.

The renewal is painless **if it happens early**. LinkedIn bypasses the consent
screen only while both are true: you are still signed in to linkedin.com, and
the current token has not yet expired. Renew late and it is a normal consent
click. Forget entirely and posting stops silently, which is the real risk while
travelling.

So: expiry is computed and stored as an absolute date at grant time, `./li
status` prints days remaining, and warnings start at 14 days.

Schedule the weekly check with:
```
./scripts/install-token-reminder.sh
```
It runs `./li status --check` every Monday at 9am and stays completely silent
until the token is within 14 days of expiring.

**One trap to remember:** "If you request a different scope than the previously
granted scope, all the previous access tokens are invalidated." Adding the
analytics scope later will kill the posting token. Both have to be granted
together, which is what `./li auth --with-analytics` does.

---

## 5. Community Management API: what blocks it

The analytics endpoint is `GET /rest/memberCreatorPostAnalytics` with scope
`r_member_postAnalytics`. Reaching it means applying for the Community
Management API, which has two tiers.

**Development tier** needs a registered legal organisation, commercial use, a
verified business email, legal name and address, a live website, and page super
admin verification. Alex has the Wyoming LLC, the live site and the company
page.

**Standard tier** is a separate application on top and adds a privacy policy
and a downloadable high resolution screen recording demonstrating each use case.

### The blocker

**There is no mailbox on hiimalex.ai.** LinkedIn states plainly that personal
addresses will not pass vetting, and the address currently on the site is a
forwarder at `email.acoffman.org`, which reads as personal. This is the one
thing standing in the way, and no amount of code moves it. Setting up real mail
on the domain unblocks the application.

**The privacy policy is now written**, at `hi-im-alex/privacy/index.html`. It is
accurate rather than boilerplate: it names Vercel Web Analytics and Microsoft
Clarity by name, says plainly that Clarity can replay a session, discloses that
the Automation Score sends typed text to Anthropic, and discloses that IP
addresses reach the server logs. It has a section describing exactly what the
LinkedIn app does, which is what the reviewer will look for. **It is not
deployed and has a placeholder contact address**, because the address depends on
the mailbox above. It needs Alex's read before it goes live.

---

## What has actually been tested, and what has not

Being precise about this matters, because there is no token yet, so **nothing in
here has ever talked to real LinkedIn.**

**Verified by running it**
* 96 tests pass, including a full publish path driven against a temporary
  database with the network mocked: the run row is written with its URN, a
  failed publish records nothing, a network failure raises rather than
  half-succeeding, and a database failure after a live publish still surfaces
  the URN so it can be recovered.
* The cooldown gate was run against the real `content.db` and blocks all three
  of the duplicate scenarios that actually went live in July.
* The schema migration was run against the real database (21 runs intact) and
  against a freshly created one, three times each, to confirm it is idempotent.
* The partial unique index genuinely rejects a second run claiming the same
  live post, while still allowing many rows with no URN for hand published posts.
* Escaping was property tested over 6,000 random strings: no dangling
  backslashes, and escaping is exactly reversible.
* `http.py` was pointed at the live API unauthenticated and returned LinkedIn's
  real `401 EMPTY_ACCESS_TOKEN`, so the transport and error capture work.
* The endpoint probe was run live with a deliberately invalid token, and both
  endpoints returned a real `401 INVALID_ACCESS_TOKEN`.

**Reasoned from the documentation, not yet confirmed live**
* That `w_member_social` really does grant `/rest/posts` for this app. The docs
  list it; only `./li probe` with a real token settles it.
* That the little format escaping renders exactly as intended on a real post.
  The rule is implemented from LinkedIn's published grammar.
* That `sub` from `/v2/userinfo` composes into a working author URN. LinkedIn
  documents that `sub` is the member id, and documents author values shaped
  like `urn:li:person:{id}`, but never states the join rule outright. This is
  the one step built on an inference rather than a quote, so a
  `400 INVALID_URN_ID` at publish time points straight here.
* The 60 day token lifespan, which is LinkedIn's documented figure.

**One bug worth recording.** The publish path originally imported `.util`
instead of `contentcrm.util`. Every publish would have gone live and then
failed to record, which is the exact untracked-post failure this design exists
to prevent. Ninety-six unit tests would not have caught it; running the real
path against a fake LinkedIn did, immediately. There is now a regression test,
and reintroducing the bug fails three tests.

## Known gaps, written down rather than left implied

**Two `./li post` runs at once could both publish.** The gates check the
database, but nothing reserves the variant, and the confirmation prompt holds
the process open for as long as it takes a human to read the copy and type.
Two terminals, or an accidental double trigger, would both pass the cooldown
check (neither has recorded a run yet) and both reach LinkedIn, producing two
real posts. The unique index on `post_urn` does not help, because two publishes
return two different URNs, and there is no unique constraint on `variant_id`.

This is unfixed. It is low likelihood with one operator working in one
terminal, and the honest fix is a lock held across the whole of `./li post`,
either a lockfile or a `BEGIN IMMEDIATE` transaction. It is written here rather
than fixed because adding a half considered lock to the one code path whose
entire job is preventing duplicate posts is worse than naming the gap.

Until it is fixed: do not run `./li post` from two terminals at once.

**Images.** Slightly over half the queue is image tagged and cannot publish
through this tool at all. That needs the Images API to obtain a
`urn:li:image:` before the post is created.

**Nothing has run against real LinkedIn.** See the section above for exactly
what has and has not been exercised.

## Why there is no scraping fallback

There is not going to be one. LinkedIn's User Agreement section 8.2 prohibits
using software, scripts or robots to scrape or copy the service, and separately
prohibits automated methods to create, comment on, like or share posts. There is
no carve out for a member's own data. Shield, a paid LinkedIn analytics company,
wound down and said Google and LinkedIn had made clear it could not continue
operating as built.

This account carries Alex's real name, his PE credential and his consulting
business. The interim way to get numbers is pasting them into the CRM by hand,
which `./crm log` already supports.

---

## Why publishing and logging are one operation

This account has produced **three separate duplicate reposts** inside the 90 day
cooldown. Every one had the same cause: a real posting event that was never
logged, so the CRM still read "never run", so the next session recommended the
same copy again.

`./crm ran` warns about prior runs, but a warning printed after the fact cannot
stop anything. So the publisher inverts it:

1. the cooldown check runs **before** the network call and **hard blocks**
2. publishing and recording the run are one operation
3. if the database write fails after a successful publish, the URN is printed
   with the exact command to recover it

That third point is not paranoia. Per post analytics only work for posts the app
created. Listing a member's own posts needs `r_member_social`, which LinkedIn
documents as restricted and available to approved users only. **A URN not
captured at publish time can never be recovered**, and that post is invisible to
analytics forever.

The gate was tested against the real database: it blocks all three of the
duplicate scenarios that actually went live.

---

## Command reference

| Command | What it does |
|---|---|
| `./li setup` | The portal checklist, with current state |
| `./li token` | Store a token made in the portal token generator. Nothing to deploy |
| `./li auth` | Connect the account, store the token, resolve the author id |
| `./li status` | Token health, days remaining, stored identity |
| `./li status --check` | Silent unless renewal is due. What cron runs |
| `./li whoami` | Call userinfo, show the member id |
| `./li probe` | Which endpoint the app may call |
| `./li preview V16` | Exactly what would be sent, including escaping. Sends nothing |
| `./li post V16 --followers 520` | Publish and record, after a typed confirmation |

Every command takes `--db` to point at a different database, matching `./crm`.

`./li post` has three gates, and they are the point of the tool:

1. **Cooldown.** Refuses if this variant has run before, or the same idea ran
   inside the platform cooldown. It fails closed: if a prior run's date cannot
   be read, or no cooldown is configured for the platform, it blocks and asks
   for a human decision rather than assuming the post is safe. `--force`
   overrides it and should be rare.
2. **Media.** Refuses if the variant is tagged `image`, `video` or `document`,
   because this version sends text only and publishing anyway would silently
   drop the visual. `--text-only` acknowledges that and proceeds.
3. **Confirmation.** Prints the copy, its outgoing character count, and which
   characters got escaped, then waits for you to type the word `publish`.
   `--yes` skips this prompt. It exists only for a future queue where a human
   already approved the copy somewhere else. Nothing on a schedule uses it and
   nothing should, because `--yes` is the one flag that removes the human.

Gates 1 and 2 are overridable on purpose. A fourth set of checks is not: an
empty body, copy over the character limit, and a variant belonging to another
platform are refused with no override at all. Those are broken input rather
than a judgement call, and `--force` used to waive them, which meant
`--force --yes` on an empty variant would have published nothing to his feed
with no prompt.

### If a publish is interrupted

If the connection drops after the request goes out, the reply is lost and
LinkedIn may still have created the post. The tool says so explicitly rather
than claiming it failed, and tells you to check your feed before retrying,
because retrying a post that already went out is exactly how a duplicate
happens. A failure to even reach LinkedIn is reported separately and is safe
to retry.

`--dry-run` builds the payload and sends nothing.
