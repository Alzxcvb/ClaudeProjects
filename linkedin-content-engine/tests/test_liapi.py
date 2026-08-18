"""Tests for the LinkedIn posting layer.

These cover the parts where a mistake is expensive rather than annoying: text
that goes out mangled on a real professional feed, a duplicate post inside the
cooldown, or a published post whose URN was never captured.
"""
import os
import random
import string
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from liapi import oauth, probe, publish
from liapi.publish import (MAX_COMMENTARY_CHARS, check_cooldown, check_hard,
                           check_media)
from liapi.littletext import escape, find_reserved, needs_escaping
from liapi import tokens


class TestLittleTextEscaping(unittest.TestCase):
    """LinkedIn: "All reserved characters need to be escaped with a backslash,
    even if those characters are not used in one of the supported elements."""

    def test_plain_text_untouched(self):
        self.assertEqual(escape("plain text no specials"), "plain text no specials")

    def test_every_reserved_character_is_escaped(self):
        for ch in "|{}@[]()<>*_~\\":
            self.assertEqual(escape(ch), "\\" + ch, "%r was not escaped" % ch)

    def test_parentheses(self):
        # The common case in Alex's copy.
        self.assertEqual(escape("I built it (in one prompt)"),
                         "I built it \\(in one prompt\\)")

    def test_backslash_becomes_double(self):
        self.assertEqual(escape("path\\to"), "path\\\\to")

    def test_real_hashtags_survive(self):
        self.assertEqual(escape("Follow best practices #coding"),
                         "Follow best practices #coding")
        self.assertEqual(escape("#AI and #ClaudeCode"), "#AI and #ClaudeCode")

    def test_hash_not_followed_by_word_is_escaped(self):
        # "issue # 5" and "C#" are not hashtags under HashtagElement ::= '#' SINGLE_WORD,
        # so they must be escaped to render as literal text.
        self.assertEqual(escape("issue # 5"), "issue \\# 5")
        self.assertEqual(escape("C# "), "C\\# ")

    def test_hashtag_preservation_can_be_turned_off(self):
        self.assertEqual(escape("Follow #coding", preserve_hashtags=False),
                         "Follow \\#coding")

    def test_newlines_are_not_touched(self):
        self.assertEqual(escape("a\nb"), "a\nb")

    def test_no_double_escaping_within_one_pass(self):
        # A single pass must never produce a backslash in front of a backslash
        # it just introduced.
        self.assertEqual(escape("(a)"), "\\(a\\)")

    def test_none_passes_through(self):
        self.assertIsNone(escape(None))

    def test_helpers(self):
        self.assertTrue(needs_escaping("has (parens)"))
        self.assertFalse(needs_escaping("clean text"))
        self.assertEqual(find_reserved("a(b)#c"), ["#", "(", ")"])


class TestLittleTextProperties(unittest.TestCase):
    """Properties that must hold for any input, not just the cases I thought of.

    A seeded random sweep, so it is deterministic and cannot flake in CI while
    still covering combinations no handwritten case would.
    """

    ALPHABET = string.printable[:95] + "\U0001F3AF" + "e" + "\uFF03"

    def _sample(self, seed, n=1500):
        rnd = random.Random(seed)
        for _ in range(n):
            yield "".join(rnd.choice(self.ALPHABET)
                          for _ in range(rnd.randint(0, 40)))

    def test_never_emits_a_dangling_backslash(self):
        # Every backslash in the output must introduce an escape pair. A
        # trailing lone backslash would make LinkedIn's parser swallow the
        # following character, or the closing quote.
        for text in self._sample(7):
            out = escape(text)
            i = 0
            while i < len(out):
                if out[i] == "\\":
                    self.assertLess(i + 1, len(out),
                                    "dangling backslash from %r -> %r" % (text, out))
                    i += 2
                else:
                    i += 1

    def test_escaping_is_reversible(self):
        # With hashtag preservation off, unescaping must recover the input
        # exactly. If this fails, some post would render differently from what
        # its author wrote.
        def unescape(t):
            out, i = [], 0
            while i < len(t):
                if t[i] == "\\" and i + 1 < len(t):
                    out.append(t[i + 1]); i += 2
                else:
                    out.append(t[i]); i += 1
            return "".join(out)

        for text in self._sample(11):
            self.assertEqual(unescape(escape(text, preserve_hashtags=False)), text)

    def test_unicode_and_newlines_pass_through(self):
        for text in ("emoji \U0001F3AF here", "caf\u00e9", "a\r\nb", "a\nb", "\t tab"):
            self.assertEqual(escape(text), text, repr(text))

    def test_hashtag_at_string_boundaries(self):
        self.assertEqual(escape("#start of it"), "#start of it")
        self.assertEqual(escape("ends with #tag"), "ends with #tag")
        self.assertEqual(escape("#a#b"), "#a#b")


class TestOAuth(unittest.TestCase):
    def test_scope_uses_percent_encoding_not_plus(self):
        url, _ = oauth.authorize_url("CID", oauth.DEFAULT_REDIRECT_URI)
        self.assertIn("scope=openid%20profile%20w_member_social", url)
        self.assertNotIn("+", url.split("scope=")[1])

    def test_redirect_uri_is_https(self):
        # LinkedIn documents an HTTPS redirect requirement.
        self.assertTrue(oauth.DEFAULT_REDIRECT_URI.startswith("https://"))

    def test_state_is_random(self):
        self.assertNotEqual(oauth.new_state(), oauth.new_state())

    def test_parse_redirect_accepts_url_and_bare_code(self):
        st = "ST"
        self.assertEqual(
            oauth.parse_redirect("https://hiimalex.ai/li/callback?code=A1&state=ST", st), "A1")
        self.assertEqual(oauth.parse_redirect("A1"), "A1")

    def test_parse_redirect_rejects_state_mismatch(self):
        with self.assertRaises(RuntimeError):
            oauth.parse_redirect("https://x/cb?code=A1&state=WRONG", "ST")

    def test_parse_redirect_surfaces_linkedin_error(self):
        with self.assertRaises(RuntimeError):
            oauth.parse_redirect("https://x/cb?error=user_cancelled_authorize&error_description=no")

    def test_url_without_code_is_not_mistaken_for_a_code(self):
        with self.assertRaises(ValueError):
            oauth.parse_redirect("https://hiimalex.ai/li/callback?state=x")
        with self.assertRaises(ValueError):
            oauth.parse_redirect("https://hiimalex.ai/li/callback")


class TestProbeClassification(unittest.TestCase):
    def test_403_means_not_entitled(self):
        self.assertEqual(probe.classify(403, "")[0], "NOT_ENTITLED")

    def test_400_means_entitled(self):
        self.assertEqual(probe.classify(400, "")[0], "ENTITLED")
        self.assertEqual(probe.classify(422, "")[0], "ENTITLED")

    def test_401_is_inconclusive(self):
        self.assertEqual(probe.classify(401, "")[0], "BAD_TOKEN")

    def test_recommend_prefers_posts_api(self):
        both = [{"key": "rest_posts", "verdict": "ENTITLED"},
                {"key": "ugc_posts", "verdict": "ENTITLED"}]
        self.assertEqual(probe.recommend(both), "rest_posts")

    def test_recommend_falls_back_to_ugc(self):
        only_ugc = [{"key": "rest_posts", "verdict": "NOT_ENTITLED"},
                    {"key": "ugc_posts", "verdict": "ENTITLED"}]
        self.assertEqual(probe.recommend(only_ugc), "ugc_posts")

    def test_recommend_none_when_neither(self):
        self.assertIsNone(probe.recommend([{"key": "rest_posts", "verdict": "NOT_ENTITLED"},
                                           {"key": "ugc_posts", "verdict": "NOT_ENTITLED"}]))


class TestPayloads(unittest.TestCase):
    def test_rest_posts_payload_shape(self):
        p = publish.build_payload("rest_posts", "urn:li:person:A", "hello")
        self.assertEqual(p["author"], "urn:li:person:A")
        self.assertEqual(p["commentary"], "hello")
        self.assertEqual(p["lifecycleState"], "PUBLISHED")
        self.assertEqual(p["distribution"]["feedDistribution"], "MAIN_FEED")

    def test_ugc_payload_shape(self):
        p = publish.build_payload("ugc_posts", "urn:li:person:A", "hello")
        sc = p["specificContent"]["com.linkedin.ugc.ShareContent"]
        self.assertEqual(sc["shareCommentary"]["text"], "hello")
        self.assertEqual(sc["shareMediaCategory"], "NONE")

    def test_unknown_endpoint_rejected(self):
        with self.assertRaises(ValueError):
            publish.build_payload("nope", "urn:li:person:A", "hi")

    def test_urn_from_header_preferred(self):
        class R(object):
            def header(self, n): return "urn:li:share:1"
            def json(self): return {"id": "urn:li:ugcPost:2"}
        self.assertEqual(publish.extract_urn(R()), "urn:li:share:1")

    def test_urn_falls_back_to_body(self):
        class R(object):
            def header(self, n): return None
            def json(self): return {"id": "urn:li:ugcPost:2"}
        self.assertEqual(publish.extract_urn(R()), "urn:li:ugcPost:2")

    def test_urn_missing_is_none(self):
        class R(object):
            def header(self, n): return None
            def json(self): return {}
        self.assertIsNone(publish.extract_urn(R()))


class _FakeConn(object):
    """Feeds check_cooldown a scripted pair of query results."""

    def __init__(self, rows):
        self.rows, self.i = rows, 0

    def execute(self, *args):
        row = self.rows[self.i] if self.i < len(self.rows) else None
        self.i += 1

        class _Cur(object):
            def fetchone(self_inner):
                return row
        return _Cur()


class TestCooldownFailsClosed(unittest.TestCase):
    """The gate exists to stop duplicate posts, so every uncertain case must
    block rather than wave the post through."""

    VARIANT = {"id": 1, "idea_id": 1, "platform": "linkedin", "body": "text"}
    CFG = {"cooldown_days": {"linkedin": 90}}

    def test_unreadable_date_blocks(self):
        # Runs on record carry approximate timestamps, so this is reachable.
        rows = [None, {"id": 9, "posted_at": "garbage", "variant_id": 3}]
        self.assertTrue(check_cooldown(_FakeConn(rows), self.VARIANT, self.CFG))

    def test_missing_cooldown_config_blocks(self):
        rows = [None, {"id": 9, "posted_at": "2026-08-01", "variant_id": 3}]
        self.assertTrue(check_cooldown(_FakeConn(rows), self.VARIANT, {"cooldown_days": {}}))

    def test_genuinely_past_cooldown_is_allowed(self):
        rows = [None, {"id": 9, "posted_at": "2020-01-01", "variant_id": 3}]
        self.assertEqual(check_cooldown(_FakeConn(rows), self.VARIANT, self.CFG), [])

    def test_no_prior_run_is_allowed(self):
        self.assertEqual(check_cooldown(_FakeConn([None, None]), self.VARIANT, self.CFG), [])

    def test_same_variant_rerun_blocks(self):
        rows = [{"id": 5, "posted_at": "2026-08-01"}, None]
        self.assertTrue(check_cooldown(_FakeConn(rows), self.VARIANT, self.CFG))

    def test_force_clears_only_the_repost_reasons(self):
        # force is a scheduling judgement a human may reasonably make.
        rows = [None, {"id": 9, "posted_at": "garbage", "variant_id": 3}]
        self.assertEqual(check_cooldown(_FakeConn(rows), self.VARIANT, self.CFG, force=True), [])


class TestHardBlockers(unittest.TestCase):
    """Defects that no flag may override.

    These were originally in the same list as the cooldown reasons, which meant
    `--force` silently waived them too: `./li post V<id> --force --yes` would
    have published a variant with an empty body, with no gate and no prompt.
    """

    def test_empty_body_is_not_forceable(self):
        for body in (None, "", "   ", "\n\n"):
            v = {"id": 1, "platform": "linkedin", "body": body}
            self.assertTrue(check_hard(v), "empty body %r must block" % body)

    def test_over_length_blocks(self):
        v = {"id": 1, "platform": "linkedin", "body": "x" * (MAX_COMMENTARY_CHARS + 1)}
        self.assertTrue(check_hard(v))

    def test_length_is_measured_after_escaping(self):
        # Escaping only grows the text, so copy that reads as under the limit
        # can cross it on the wire. Measuring the raw body would miss this.
        body = "(" * (MAX_COMMENTARY_CHARS - 10)
        self.assertLess(len(body), MAX_COMMENTARY_CHARS)
        self.assertTrue(check_hard({"id": 1, "platform": "linkedin", "body": body},
                                   "rest_posts"))

    def test_ugc_endpoint_measures_raw_text(self):
        # ugcPosts takes plain text, so nothing expands.
        body = "(" * (MAX_COMMENTARY_CHARS - 10)
        self.assertEqual(check_hard({"id": 1, "platform": "linkedin", "body": body},
                                    "ugc_posts"), [])

    def test_wrong_platform_blocks(self):
        for plat in ("x", "instagram", None):
            v = {"id": 1, "platform": plat, "body": "fine"}
            self.assertTrue(check_hard(v), "platform %r must block" % plat)

    def test_good_variant_passes(self):
        self.assertEqual(check_hard({"id": 1, "platform": "linkedin", "body": "fine"}), [])


class TestMediaGuard(unittest.TestCase):
    """An image-tagged variant must never go out silently as text."""

    def test_image_variant_is_blocked(self):
        v = {"id": 20, "media_type": "image"}
        self.assertTrue(check_media(v))

    def test_video_and_document_also_blocked(self):
        for kind in ("video", "document", "IMAGE"):
            self.assertTrue(check_media({"id": 1, "media_type": kind}), kind)

    def test_text_variant_passes(self):
        self.assertEqual(check_media({"id": 1, "media_type": "text"}), [])

    def test_null_media_type_passes(self):
        self.assertEqual(check_media({"id": 1, "media_type": None}), [])

    def test_acknowledgement_overrides(self):
        self.assertEqual(check_media({"id": 1, "media_type": "image"}, text_only_ack=True), [])


class TestTokenExpiry(unittest.TestCase):
    def test_sixty_day_token_math(self):
        rec = tokens.record_grant({"access_token": "x", "expires_in": 5184000},
                                  "w_member_social", "cid", path=False)
        self.assertIn(tokens.days_left(rec), (59, 60))
        self.assertFalse(tokens.is_expired(rec))
        self.assertFalse(tokens.needs_attention(rec))

    def test_expired_token_detected(self):
        rec = {"expires_at": "2020-01-01 00:00:00"}
        self.assertTrue(tokens.is_expired(rec))
        self.assertIn("EXPIRED", tokens.summary(rec))

    def test_missing_token_summary(self):
        self.assertIn("no token stored", tokens.summary(None))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestPublishEndToEnd(unittest.TestCase):
    """Drive the real publish path against a temporary database and a fake
    LinkedIn.

    This class exists because of a specific bug. `_record_run` imported
    `.util` instead of `contentcrm.util`, so every publish would have gone LIVE
    and then failed to record: exactly the untracked-post failure the whole
    design is meant to prevent. Eighty-eight unit tests passed while that was
    broken, because none of them executed this path. Mock the network, never
    the code under test.
    """

    def setUp(self):
        import shutil
        import sqlite3
        import tempfile

        from contentcrm.config import load_config
        from contentcrm.db import connect

        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "t.db")
        # A minimal database rather than a copy of the real one, so the test
        # never depends on Alex's live data.
        conn = connect(self.db)
        conn.execute("INSERT INTO ideas (id, slug, title, created_at) VALUES (1,'s','t','2026-01-01')")
        conn.execute("INSERT INTO variants (id, idea_id, platform, body, media_type, created_at)"
                     " VALUES (1,1,'linkedin','Hello (world)','text','2026-01-01')")
        conn.commit()
        self.conn = conn
        self.cfg = load_config()
        self.variant = dict(conn.execute("SELECT * FROM variants WHERE id=1").fetchone())
        self.calls = []
        self._real_post = publish.http.post

    def tearDown(self):
        publish.http.post = self._real_post

    def _fake(self, status, headers, body=""):
        outer = self

        class _R(object):
            def __init__(self):
                self.status, self.headers, self.body = status, headers, body
                self.ok = 200 <= status < 300

            def header(self, name):
                for k, v in self.headers.items():
                    if k.lower() == name.lower():
                        return v
                return None

            def json(self):
                return None

        def _post(url, headers=None, body=None, timeout=30):
            outer.calls.append({"url": url, "headers": headers, "body": body})
            return _R()
        publish.http.post = _post

    def test_publish_records_the_run_with_its_urn(self):
        self._fake(201, {"x-restli-id": "urn:li:share:123"})
        res = publish.publish(self.conn, self.cfg, self.variant, "TOK",
                              "urn:li:person:ME", "rest_posts",
                              followers=500, force=True)
        row = self.conn.execute("SELECT * FROM runs WHERE id=?", (res["run_id"],)).fetchone()
        self.assertEqual(row["post_urn"], "urn:li:share:123")
        self.assertEqual(row["variant_id"], 1)
        self.assertEqual(row["followers_at_post"], 500)
        self.assertIn("urn:li:share:123", row["post_url"])

    def test_version_header_is_sent_on_the_posts_api(self):
        self._fake(201, {"x-restli-id": "urn:li:share:1"})
        publish.publish(self.conn, self.cfg, self.variant, "TOK",
                        "urn:li:person:ME", "rest_posts", force=True)
        self.assertEqual(self.calls[-1]["headers"]["Linkedin-Version"], probe.LINKEDIN_VERSION)

    def test_failed_publish_records_nothing(self):
        self._fake(403, {}, '{"code":"ACCESS_DENIED"}')
        before = self.conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
        with self.assertRaises(publish.PublishFailed):
            publish.publish(self.conn, self.cfg, self.variant, "TOK",
                            "urn:li:person:ME", "rest_posts", force=True)
        after = self.conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
        self.assertEqual(before, after, "a failed publish must not leave a phantom run")

    def test_network_failure_is_a_publish_failure(self):
        self._fake(0, {}, "network error")
        with self.assertRaises(publish.PublishFailed):
            publish.publish(self.conn, self.cfg, self.variant, "TOK",
                            "urn:li:person:ME", "rest_posts", force=True)

    def test_missing_urn_raises_rather_than_losing_the_post(self):
        self._fake(201, {})
        with self.assertRaises(publish.RecordingFailed):
            publish.publish(self.conn, self.cfg, self.variant, "TOK",
                            "urn:li:person:ME", "rest_posts", force=True)

    def test_recording_failure_still_carries_the_urn(self):
        self._fake(201, {"x-restli-id": "urn:li:share:999"})
        real = publish._record_run

        def boom(*a, **k):
            raise RuntimeError("disk full")
        publish._record_run = boom
        try:
            with self.assertRaises(publish.RecordingFailed) as ctx:
                publish.publish(self.conn, self.cfg, self.variant, "TOK",
                                "urn:li:person:ME", "rest_posts", force=True)
            # The URN must survive, or analytics can never read that post.
            self.assertEqual(ctx.exception.urn, "urn:li:share:999")
        finally:
            publish._record_run = real

    def test_dry_run_sends_nothing(self):
        self._fake(201, {"x-restli-id": "urn:li:share:1"})
        res = publish.publish(self.conn, self.cfg, self.variant, "TOK",
                              "urn:li:person:ME", "rest_posts",
                              force=True, dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertEqual(self.calls, [], "dry run must not touch the network")

    def test_the_same_live_post_cannot_be_recorded_twice(self):
        import sqlite3
        self._fake(201, {"x-restli-id": "urn:li:share:dup"})
        publish.publish(self.conn, self.cfg, self.variant, "TOK",
                        "urn:li:person:ME", "rest_posts", force=True)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO runs (variant_id,platform,posted_at,created_at,post_urn)"
                " VALUES (1,'linkedin','2026-09-01','x','urn:li:share:dup')")
            self.conn.commit()


class TestUrnRecovery(unittest.TestCase):
    """The disaster path must restore the invariant, not just leave a note.

    If a post goes live and the run cannot be recorded, the printed recovery
    command has to put the URN in the `post_urn` COLUMN. Writing it into free
    text `notes` would look like a save while leaving the post permanently
    invisible to the analytics API, which reads the column.
    """

    def setUp(self):
        import tempfile
        from contentcrm.db import connect
        self.db = os.path.join(tempfile.mkdtemp(), "r.db")
        conn = connect(self.db)
        conn.execute("INSERT INTO ideas (id,slug,title,created_at) VALUES (1,'s','t','2026-01-01')")
        conn.execute("INSERT INTO variants (id,idea_id,platform,body,created_at)"
                     " VALUES (1,1,'linkedin','x','2026-01-01')")
        conn.commit()
        conn.close()

    def test_crm_ran_urn_lands_in_the_column(self):
        from contentcrm.cli import main as crm_main
        crm_main(["--db", self.db, "ran", "V1", "--urn", "urn:li:share:555"])
        import sqlite3
        conn = sqlite3.connect(self.db)
        row = conn.execute("SELECT post_urn, notes FROM runs").fetchone()
        self.assertEqual(row[0], "urn:li:share:555")

    def test_crm_ran_without_urn_leaves_it_null(self):
        from contentcrm.cli import main as crm_main
        crm_main(["--db", self.db, "ran", "V1"])
        import sqlite3
        conn = sqlite3.connect(self.db)
        self.assertIsNone(conn.execute("SELECT post_urn FROM runs").fetchone()[0])


class TestAmbiguousNetworkOutcome(unittest.TestCase):
    """A lost reply must never be reported as "nothing went live".

    LinkedIn may have created the post before the connection died. Telling the
    operator it definitely failed invites a retry, and the retry is a duplicate.
    """

    def test_timeout_after_send_is_ambiguous_not_failure(self):
        import socket
        import urllib.request
        from liapi import http as lihttp

        real = urllib.request.urlopen

        def boom(*a, **k):
            raise socket.timeout("timed out")
        urllib.request.urlopen = boom
        try:
            resp = lihttp.post("https://api.linkedin.com/rest/posts", headers={}, body={})
        finally:
            urllib.request.urlopen = real
        self.assertTrue(resp.ambiguous)
        self.assertEqual(resp.status, lihttp.STATUS_AMBIGUOUS)

    def test_connect_failure_is_not_ambiguous(self):
        import urllib.error
        import urllib.request
        from liapi import http as lihttp

        real = urllib.request.urlopen

        def boom(*a, **k):
            raise urllib.error.URLError("connection refused")
        urllib.request.urlopen = boom
        try:
            resp = lihttp.post("https://api.linkedin.com/rest/posts", headers={}, body={})
        finally:
            urllib.request.urlopen = real
        self.assertFalse(resp.ambiguous)
        self.assertEqual(resp.status, lihttp.STATUS_NOT_SENT)

    def test_publish_raises_ambiguous_and_records_nothing(self):
        import socket
        import tempfile
        import urllib.request

        from contentcrm.config import load_config
        from contentcrm.db import connect

        db = os.path.join(tempfile.mkdtemp(), "a.db")
        conn = connect(db)
        conn.execute("INSERT INTO ideas (id,slug,title,created_at) VALUES (1,'s','t','2026-01-01')")
        conn.execute("INSERT INTO variants (id,idea_id,platform,body,created_at)"
                     " VALUES (1,1,'linkedin','hello','2026-01-01')")
        conn.commit()
        variant = dict(conn.execute("SELECT * FROM variants WHERE id=1").fetchone())

        real = urllib.request.urlopen

        def boom(*a, **k):
            raise socket.timeout("timed out")
        urllib.request.urlopen = boom
        try:
            with self.assertRaises(publish.PublishAmbiguous):
                publish.publish(conn, load_config(), variant, "TOK",
                                "urn:li:person:ME", "rest_posts", force=True)
        finally:
            urllib.request.urlopen = real
        self.assertEqual(conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"], 0)


class TestPreviewAccuracy(unittest.TestCase):
    def test_escaped_chars_excludes_preserved_hashtags(self):
        from liapi.littletext import escaped_chars, find_reserved
        text = "Check out #AI_trends and (this) too"
        self.assertEqual(find_reserved(text), ["#", "(", ")", "_"])
        # The # and the _ live inside a preserved hashtag, so they are NOT
        # escaped. Reporting them as escaped would be a lie on the approval screen.
        self.assertEqual(escaped_chars(text), ["(", ")"])


class TestNoNetworkExceptionEscapes(unittest.TestCase):
    """Nothing at the socket layer may escape http.request uncaught.

    An uncaught exception mid-publish is the same failure as the original
    import bug: the post goes live, the URN is lost, and the operator gets a
    traceback instead of a recovery path.
    """

    def _raise_from_urlopen(self, exc):
        import urllib.request
        from liapi import http as lihttp
        real = urllib.request.urlopen

        def boom(*a, **k):
            raise exc
        urllib.request.urlopen = boom
        try:
            return lihttp.post("https://api.linkedin.com/rest/posts", headers={}, body={})
        finally:
            urllib.request.urlopen = real

    def test_no_network_exception_escapes(self):
        import socket
        import ssl
        import urllib.error
        for exc in (socket.timeout("t"), TimeoutError("t"), urllib.error.URLError("r"),
                    ConnectionResetError("r"), socket.gaierror("dns"), ssl.SSLError("s"),
                    ssl.SSLEOFError("e"), BrokenPipeError("b"), OSError("o")):
            resp = self._raise_from_urlopen(exc)
            self.assertIn(resp.status, (0, -1), "%r produced %s" % (exc, resp.status))

    def test_failures_before_sending_are_not_ambiguous(self):
        # Nothing left the machine, so retrying is safe and the operator should
        # not be told to go inspect their feed.
        import socket
        import urllib.error
        from liapi import http as lihttp
        for exc in (urllib.error.URLError("refused"), socket.gaierror("dns")):
            self.assertEqual(self._raise_from_urlopen(exc).status, lihttp.STATUS_NOT_SENT,
                             "%r must be NOT_SENT" % exc)

    def test_failures_after_sending_are_ambiguous(self):
        import socket
        from liapi import http as lihttp
        for exc in (socket.timeout("t"), ConnectionResetError("r"), BrokenPipeError("b")):
            self.assertEqual(self._raise_from_urlopen(exc).status, lihttp.STATUS_AMBIGUOUS,
                             "%r must be AMBIGUOUS" % exc)

    def test_non_network_exceptions_still_propagate(self):
        # These are not network conditions and must never be converted into a
        # publish outcome.
        for exc in (KeyboardInterrupt(), MemoryError()):
            with self.assertRaises(type(exc)):
                self._raise_from_urlopen(exc)


class TestNoBadInputReachesLinkedIn(unittest.TestCase):
    """The whole-gate guarantee, asserted rather than assumed.

    Individual gate functions are unit tested above. This checks the property
    that actually matters: across every override flag, nothing broken reaches
    the network. It exists because the original bug was precisely that --force
    waived checks it was never meant to touch, and that was invisible until
    someone traced the combination.
    """

    BROKEN = [
        ("empty body", "linkedin", None),
        ("whitespace body", "linkedin", "   "),
        ("over length raw", "linkedin", "x" * 3500),
        ("over length after escaping", "linkedin", "(" * 2995),
        ("wrong platform", "x", "fine copy"),
        ("wrong platform 2", "instagram", "fine copy"),
    ]

    def setUp(self):
        import tempfile
        from contentcrm.config import load_config
        from contentcrm.db import connect
        self.conn = connect(os.path.join(tempfile.mkdtemp(), "gate.db"))
        self.conn.execute("INSERT INTO ideas (id,slug,title,created_at)"
                          " VALUES (1,'s','t','2026-01-01')")
        self.conn.commit()
        self.cfg = load_config()
        self.sent = []
        self._real_post = publish.http.post
        outer = self

        def tripwire(url, headers=None, body=None, timeout=30):
            outer.sent.append(url)
            raise AssertionError("bad input reached LinkedIn: %s" % url)
        publish.http.post = tripwire

    def tearDown(self):
        publish.http.post = self._real_post

    def _variant(self, platform, body):
        cur = self.conn.execute(
            "INSERT INTO variants (idea_id,platform,body,created_at)"
            " VALUES (1,?,?,'2026-01-01')", (platform, body))
        self.conn.commit()
        return dict(self.conn.execute("SELECT * FROM variants WHERE id=?",
                                      (cur.lastrowid,)).fetchone())

    def test_broken_variants_never_reach_the_network(self):
        for label, platform, body in self.BROKEN:
            for force in (False, True):
                variant = self._variant(platform, body)
                with self.assertRaises(publish.PublishBlocked,
                                       msg="%s force=%s was not blocked" % (label, force)):
                    publish.publish(self.conn, self.cfg, variant, "TOK",
                                    "urn:li:person:ME", "rest_posts", force=force)
        self.assertEqual(self.sent, [], "something broken reached LinkedIn")
