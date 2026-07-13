"""Markdown library import: mdnotes layout, flat files, idempotency, and the
never-mutate-a-variant-that-ran rule."""
import unittest

from contentcrm.importers import import_markdown_dir

from .helpers import CrmTestCase

MDNOTES_PAGE = """---
id: 01KWZZAQAN8T809XZNMFYCEHVH
title: Email Costs Five Figures
createdAt: 2026-07-08T04:21:12.660Z
updatedAt: 2026-07-08T06:27:18.140Z
---
"I'll just clear my email" is a five-figure decision.

Nobody hires their best self for inbox triage.
"""

FLAT_WITH_H1 = """# Hackathon Winners Changed

Hackathon winners used to be engineers in hoodies.

Now they're lawyers and doctors.
"""

BARE = "Four hours a week of copy-pasting is a month of vacation.\n"

STUB = """---
title: Just A Title
---
"""

X_POST = """---
title: Short X Take
platform: x
tags: ai, hiring
---
Hire AI before you hire humans.
"""


class TestImport(CrmTestCase):
    def setUp(self):
        super().setUp()
        self.lib = self.dir / "swipe"
        (self.lib / "email-costs").mkdir(parents=True)
        (self.lib / "email-costs" / "index.md").write_text(MDNOTES_PAGE)
        (self.lib / "hackathons.md").write_text(FLAT_WITH_H1)
        (self.lib / "copy paste tax.md").write_text(BARE)
        (self.lib / "stub").mkdir()
        (self.lib / "stub" / "index.md").write_text(STUB)
        (self.lib / "x-take.md").write_text(X_POST)

    def test_import_creates_ideas_and_variants(self):
        summary = import_markdown_dir(self.conn, self.lib, "linkedin", self.cfg)
        self.assertEqual(len(summary["created"]), 4)
        self.assertEqual(summary["skipped_empty"], ["stub/index.md"])

        idea = self.one("SELECT * FROM ideas WHERE slug = 'email-costs-five-figures'")
        self.assertEqual(idea["title"], "Email Costs Five Figures")
        self.assertEqual(idea["source"], "markdown-import")
        variant = self.one("SELECT * FROM variants WHERE idea_id = ?", idea["id"])
        self.assertIn("five-figure decision", variant["body"])
        self.assertEqual(variant["platform"], "linkedin")

        # H1 becomes the title and is stripped from the body
        h1_idea = self.one("SELECT * FROM ideas WHERE slug = 'hackathon-winners-changed'")
        h1_variant = self.one("SELECT * FROM variants WHERE idea_id = ?", h1_idea["id"])
        self.assertNotIn("# Hackathon", h1_variant["body"])

        # filename fallback title
        self.assertIsNotNone(self.one("SELECT * FROM ideas WHERE slug = 'copy-paste-tax'"))

        # frontmatter platform + tags respected
        x_idea = self.one("SELECT * FROM ideas WHERE slug = 'short-x-take'")
        self.assertIn("hiring", x_idea["tags"])
        x_variant = self.one("SELECT * FROM variants WHERE idea_id = ?", x_idea["id"])
        self.assertEqual(x_variant["platform"], "x")

    def test_reimport_is_idempotent(self):
        import_markdown_dir(self.conn, self.lib, "linkedin", self.cfg)
        summary = import_markdown_dir(self.conn, self.lib, "linkedin", self.cfg)
        self.assertEqual(summary["created"], [])
        self.assertEqual(len(summary["skipped_unchanged"]), 4)
        self.assertEqual(self.count("variants"), 4)

    def test_edited_unposted_draft_updates_in_place(self):
        import_markdown_dir(self.conn, self.lib, "linkedin", self.cfg)
        (self.lib / "copy paste tax.md").write_text(BARE + "\nNew closing line.\n")
        summary = import_markdown_dir(self.conn, self.lib, "linkedin", self.cfg)
        self.assertEqual(summary["updated"], ["copy paste tax.md"])
        self.assertEqual(self.count("variants"), 4)
        v = self.one("SELECT * FROM variants v JOIN ideas i ON i.id = v.idea_id"
                     " WHERE i.slug = 'copy-paste-tax'")
        self.assertIn("New closing line", v["body"])

    def test_edited_posted_draft_becomes_child_variant(self):
        import_markdown_dir(self.conn, self.lib, "linkedin", self.cfg)
        v = self.one("SELECT v.* FROM variants v JOIN ideas i ON i.id = v.idea_id"
                     " WHERE i.slug = 'copy-paste-tax'")
        self.crm("ran", f"V{v['id']}", "--at", "2026-07-01 09:00", "--followers", "400")
        (self.lib / "copy paste tax.md").write_text(BARE + "\nRewritten after it ran.\n")
        summary = import_markdown_dir(self.conn, self.lib, "linkedin", self.cfg)
        self.assertEqual(summary["rewritten"], ["copy paste tax.md"])
        child = self.one(
            "SELECT * FROM variants WHERE derived_from_variant_id = ?", v["id"])
        self.assertIsNotNone(child)
        self.assertEqual(child["idea_id"], v["idea_id"])
        original = self.one("SELECT * FROM variants WHERE id = ?", v["id"])
        self.assertNotIn("Rewritten after it ran", original["body"])


if __name__ == "__main__":
    unittest.main()
