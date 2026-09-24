"""Tests for council.prompts. No live model calls: these only exercise the
prompt-string builders and parse_verdict against fake/canned text."""
import unittest

from council import prompts


class _FakePersona:
    def __init__(self, key, name, body):
        self.key = key
        self.name = name
        self.body = body


BULL = _FakePersona("bull", "Bull", "# Bull\n\nI expect things to go well.")
BEAR = _FakePersona("bear", "Bear", "# Bear\n\nI expect things to go badly.")


class CasePromptTest(unittest.TestCase):
    def test_system_is_persona_body(self):
        system, _prompt = prompts.build_case_prompt(BULL, "will X happen?")
        self.assertEqual(system, BULL.body)

    def test_prompt_includes_question_and_word_cap_and_no_naming_rule(self):
        _system, prompt = prompts.build_case_prompt(BULL, "will X happen?")
        self.assertIn("will X happen?", prompt)
        self.assertIn("300", prompt)
        self.assertIn("Do not name your persona", prompt)
        self.assertIn("first person", prompt.lower())


class RebuttalPromptTest(unittest.TestCase):
    def test_prompt_includes_own_and_opposing_case_and_word_cap(self):
        _system, prompt = prompts.build_rebuttal_prompt(
            BEAR, "will X happen?", "my case text", "the other side's case text"
        )
        self.assertIn("my case text", prompt)
        self.assertIn("the other side's case text", prompt)
        self.assertIn("200", prompt)
        self.assertIn("Do not name your persona", prompt)


class BlindProviderTokensTest(unittest.TestCase):
    def test_chatgpt_and_gpt5_redacted(self):
        out = prompts.blind("I run on ChatGPT, specifically GPT-5.", ["Bull"])
        self.assertNotIn("ChatGPT", out)
        self.assertNotIn("GPT-5", out)
        self.assertIn("[redacted]", out)

    def test_claude_codex_anthropic_openai_sonnet_opus_haiku_redacted(self):
        text = (
            "Claude and Codex are both fine, made by Anthropic and OpenAI, "
            "whether Sonnet, Opus, or Haiku."
        )
        out = prompts.blind(text, [])
        for token in ("Claude", "Codex", "Anthropic", "OpenAI", "Sonnet", "Opus", "Haiku"):
            self.assertNotIn(token, out)

    def test_provider_token_redacted_case_insensitively_mid_word(self):
        out = prompts.blind("anthropic's approach differs.", [])
        self.assertNotIn("anthropic", out.lower())


class BlindPersonaNameTest(unittest.TestCase):
    def test_bull_market_survives_unchanged_under_persona_bull(self):
        text = "the bull market is strong"
        out = prompts.blind(text, ["Bull"])
        self.assertEqual(out, text)

    def test_self_reference_as_the_bull_is_redacted(self):
        out = prompts.blind("As the Bull, I think this holds.", ["Bull"])
        self.assertNotIn("Bull", out)
        self.assertIn("[redacted]", out)

    def test_self_reference_i_am_persona_is_redacted(self):
        out = prompts.blind("I am the Bear and I disagree.", ["Bear"])
        self.assertNotIn("Bear", out)

    def test_self_reference_speaking_as_persona_is_redacted(self):
        out = prompts.blind("Speaking as Bull, this is my view.", ["Bull"])
        self.assertNotIn("Bull", out)

    def test_bare_mention_of_persona_name_not_self_reference_survives(self):
        # B1: only self-reference patterns are scrubbed, not every mention.
        text = "Bull's case explains the trend."
        out = prompts.blind(text, ["Bull"])
        self.assertEqual(out, text)


class JudgePromptTest(unittest.TestCase):
    def _record(self, wins=0, resolved=0):
        rate = (wins / resolved) if resolved else None
        return {"wins": wins, "resolved": resolved, "rate": rate}

    def test_no_forbidden_tokens_and_has_position_labels_and_record_sentence(self):
        case1 = "I am the Bull, running on Claude via codex. Things look good."
        rebuttal1 = "As the Bull, I still disagree with the pessimist."
        case2 = "I am the Bear, and I use GPT-5 sometimes."
        rebuttal2 = "Speaking as Bear, the risks remain."

        prompt = prompts.build_judge_prompt(
            "will X happen?",
            ["Bull", "Bear"],
            case1,
            rebuttal1,
            case2,
            rebuttal2,
            self._record(wins=2, resolved=3),
            self._record(),
        )

        lowered = prompt.lower()
        for forbidden in ("bull", "bear", "claude", "codex", "gpt-5", "gpt5"):
            self.assertNotIn(forbidden, lowered)

        self.assertIn("Position 1", prompt)
        self.assertIn("Position 2", prompt)
        self.assertIn("resolved record", prompt)

    def test_record_sentence_includes_wins_and_resolved_counts(self):
        prompt = prompts.build_judge_prompt(
            "q",
            [],
            "case1", "rebuttal1", "case2", "rebuttal2",
            self._record(wins=3, resolved=5),
            self._record(wins=1, resolved=4),
        )
        self.assertIn("3 wins", prompt)
        self.assertIn("5 resolved questions", prompt)
        self.assertIn("1 wins", prompt)
        self.assertIn("4 resolved questions", prompt)

    def test_record_sentence_no_resolved_record_yet_branch(self):
        prompt = prompts.build_judge_prompt(
            "q",
            [],
            "case1", "rebuttal1", "case2", "rebuttal2",
            self._record(),
            self._record(),
        )
        self.assertIn("no resolved record yet", prompt)

    def test_asks_for_json_only(self):
        prompt = prompts.build_judge_prompt(
            "q", [], "c1", "r1", "c2", "r2", self._record(), self._record()
        )
        self.assertIn("Return only JSON", prompt)
        self.assertIn("winner", prompt)
        self.assertIn("confidence", prompt)


class ParseVerdictTest(unittest.TestCase):
    VALID = (
        '{"winner": "1", "confidence": 0.8, "key_reason": "clearer case", '
        '"would_change_mind": "new evidence"}'
    )

    def test_bare_json(self):
        verdict = prompts.parse_verdict(self.VALID)
        self.assertEqual(verdict["winner"], "1")
        self.assertEqual(verdict["confidence"], 0.8)
        self.assertEqual(verdict["key_reason"], "clearer case")
        self.assertEqual(verdict["would_change_mind"], "new evidence")

    def test_fenced_json_with_language_tag(self):
        fenced = f"Here is my verdict:\n```json\n{self.VALID}\n```\nThanks."
        verdict = prompts.parse_verdict(fenced)
        self.assertEqual(verdict["winner"], "1")

    def test_fenced_json_no_language_tag(self):
        fenced = f"```\n{self.VALID}\n```"
        verdict = prompts.parse_verdict(fenced)
        self.assertEqual(verdict["confidence"], 0.8)

    def test_json_with_surrounding_prose(self):
        wrapped = f"Sure, here's my ruling.\n{self.VALID}\nHope that helps!"
        verdict = prompts.parse_verdict(wrapped)
        self.assertEqual(verdict["winner"], "1")

    def test_garbage_raises(self):
        with self.assertRaises(prompts.VerdictParseError):
            prompts.parse_verdict("I refuse to answer in JSON today.")

    def test_no_braces_at_all_raises(self):
        with self.assertRaises(prompts.VerdictParseError):
            prompts.parse_verdict("winner: 1, confidence: 0.8")

    def test_malformed_json_raises(self):
        with self.assertRaises(prompts.VerdictParseError):
            prompts.parse_verdict('{"winner": "1", "confidence": 0.8,}')

    def test_winner_must_be_1_or_2_string(self):
        bad = '{"winner": 1, "confidence": 0.5, "key_reason": "x", "would_change_mind": "y"}'
        with self.assertRaises(prompts.VerdictParseError):
            prompts.parse_verdict(bad)

        bad2 = '{"winner": "3", "confidence": 0.5, "key_reason": "x", "would_change_mind": "y"}'
        with self.assertRaises(prompts.VerdictParseError):
            prompts.parse_verdict(bad2)

    def test_confidence_out_of_range_raises(self):
        bad = '{"winner": "2", "confidence": 1.5, "key_reason": "x", "would_change_mind": "y"}'
        with self.assertRaises(prompts.VerdictParseError):
            prompts.parse_verdict(bad)

        bad2 = '{"winner": "2", "confidence": -0.1, "key_reason": "x", "would_change_mind": "y"}'
        with self.assertRaises(prompts.VerdictParseError):
            prompts.parse_verdict(bad2)

    def test_confidence_boundaries_0_and_1_are_valid(self):
        low = '{"winner": "1", "confidence": 0, "key_reason": "x", "would_change_mind": "y"}'
        high = '{"winner": "2", "confidence": 1, "key_reason": "x", "would_change_mind": "y"}'
        self.assertEqual(prompts.parse_verdict(low)["confidence"], 0.0)
        self.assertEqual(prompts.parse_verdict(high)["confidence"], 1.0)

    def test_missing_key_reason_raises(self):
        bad = '{"winner": "1", "confidence": 0.5, "would_change_mind": "y"}'
        with self.assertRaises(prompts.VerdictParseError):
            prompts.parse_verdict(bad)

    def test_incomplete_object_missing_required_fields_raises(self):
        # first-"{"-to-last-"}" extraction pulls out a well-formed but
        # schema-incomplete object here; it must still be rejected.
        with self.assertRaises(prompts.VerdictParseError):
            prompts.parse_verdict('[{"winner": "1"}]')


if __name__ == "__main__":
    unittest.main()


class BlindSelfReferenceEdgeTest(unittest.TestCase):
    def test_name_used_as_ordinary_noun_survives(self):
        from council.prompts import blind
        for text in ("As the bull market shows, prices rise.",
                     "The fund has the bull case covered."):
            self.assertEqual(blind(text, ["Bull"]), text)

    def test_self_reference_still_redacted(self):
        from council.prompts import blind
        self.assertNotIn("Bull", blind("As the Bull, I think prices rise.", ["Bull"]))
        self.assertNotIn("Bull", blind("I am Bull. Prices rise.", ["Bull"]))
