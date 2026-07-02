# DROP post-OTP recon → implement `_click_submit` (2026-07-03)

Blocker being fixed: `submit()` has no pause point for human OTP entry, so nobody
has ever seen the post-OTP screens and `_click_submit` is still a stub.

## Plan

- [x] Read client.py / test_drop.py / project-erasure.md resume point
- [x] Write `scripts/drop_post_otp_recon.py` — headed browser, reuses
      BrowserSession + `_fill_form` to reach "Send code", then human-paced
      capture loop (screenshot + HTML per screen) into `state/drop/snapshots/`
- [x] Tell Alex what to run and what to expect (profile via
      `python3 -m erasure.cli init` first; Tailscale "boxy" exit node ON)
- [ ] **WAITING ON ALEX** — walk the live flow, enter OTP, capture each screen
- [ ] Read saved HTML snapshots → extract accessible labels/roles per screen
- [ ] Implement `_click_submit` (get_by_label / get_by_role pattern, return
      Optional[str] confirmation code)
- [ ] Extend `_FakePage` + add `_click_submit` tests in tests/test_drop.py;
      full pytest green (baseline: 143 passing)
- [ ] NO live `--confirm` run unless Alex explicitly says go
- [ ] Update NEXT SESSION RESUME POINT in project-erasure.md with findings

## Conventions to honor
- Stage by explicit path; inspect `git diff --cached` before commit
- Commit + push after each logical piece
- If the Gateway rejects Alex before "Send code": stop, report exact rejection
  point (IP or phone precondition unsolved), do not guess selectors

## Review
(filled in when done)
