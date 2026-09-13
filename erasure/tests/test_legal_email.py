"""Tests for filling the deletion email templates that ship with the directory.

Every test builds its own fake profile. Most build their own fake directory
entries too, so a wording change upstream cannot turn into a failing assertion.

The exceptions are the tests that guard the bundled dataset. Those scan every
shipped template with a deliberately wider pattern than the one the tool uses,
and assert that nothing it flags survives into the rendered message. They are
written that way on purpose: a blank shape the tool does not recognise is the
one failure that matters here, because the user is told the message is ready
and sends a sample address to a real company.

That scan is keyed on meaning as well as shape. It looks for any token that
names a field where a value belongs, in any casing and with no delimiter
needed, because round 2 searched for delimiters only and seven entries shipping
a bare YOUR_EMAIL or LEETIFYACCOUNTID passed it. It keeps its own copy of the
allow list, so widening the module's list cannot widen this one.
"""

from __future__ import annotations

import json
import re

import pytest
from click.testing import CliRunner

from erasure.accounts.justdelete import (
    DeletionEntry,
    _host,
    load_directory,
    match_candidates,
    match_entry,
)
from erasure.cli import cli
from erasure.legal.email_templates import (
    ACCOUNT_ID,
    _PLACEHOLDER_RE,
    DEFAULT_SUBJECT,
    EMAIL,
    NAME,
    OTHER,
    PHONE,
    REASON,
    UNKNOWN,
    USERNAME,
    TemplateFields,
    classify_placeholder,
    decode_mailto_escapes,
    fields_from_profile,
    fill_template_text,
    has_email_template,
    missing_field_lines,
    render_email_request,
)
from erasure.profile import UserProfile

MARKER = "<<FILL IN:"


def _profile() -> UserProfile:
    return UserProfile(
        name="Jane Q Public",
        emails=["jane@example.com", "jq@example.org"],
        phones=["+1-555-0100"],
    )


def _fields() -> TemplateFields:
    return TemplateFields(
        name="Jane Q Public",
        email="jane@example.com",
        username="jqpublic",
        phone="+1-555-0100",
    )


def _entry(**kwargs) -> DeletionEntry:
    base = dict(
        name="Fakebook",
        domains=["fakebook.example"],
        difficulty="hard",
        email="privacy@fakebook.example",
        email_subject="Delete my Fakebook account",
        email_body="Please delete my account, my username is XXXXXX.",
    )
    base.update(kwargs)
    return DeletionEntry(**base)


# --- placeholder detection, one test per style present in the dataset --------


def test_x_run_is_filled_from_context():
    out, filled, missing = fill_template_text("My username is XXXXXX.", _fields())
    assert out == "My username is jqpublic."
    assert filled == [USERNAME] and missing == []


def test_y_run_is_detected_and_left_blank():
    """cTrader asks for a passport with a YYYYY run. A passport is never filled."""
    out, _, missing = fill_template_text(
        "My e-mail is XXXXX and the passport is YYYYY.", _fields()
    )
    assert "jane@example.com" in out
    assert MARKER in out
    assert missing == [ACCOUNT_ID]


def test_angle_token_is_read_from_the_token_itself():
    out, filled, missing = fill_template_text(
        "Please delete the account for <YOUR_EMAIL>, thank you.", _fields()
    )
    assert out == "Please delete the account for jane@example.com, thank you."
    assert filled == [EMAIL] and missing == []


def test_all_caps_bracket_note_is_never_filled():
    out, filled, missing = fill_template_text(
        "Number of Nominees: [NUMBER OR 0]", _fields()
    )
    assert MARKER in out and "[NUMBER OR 0]" not in out
    assert filled == [] and missing == [ACCOUNT_ID]


def test_mixed_case_bracket_is_left_alone_as_literal_text():
    """CoinBR decorates its subject with brackets. That is not a placeholder."""
    out, filled, missing = fill_template_text(
        "[ Permanently Account Deletion Request ]", _fields()
    )
    assert out == "[ Permanently Account Deletion Request ]"
    assert filled == [] and missing == []


def test_parenthetical_instruction_is_labelled_but_never_filled():
    """MEXC writes instructions for a person. Filling inside one makes nonsense."""
    out, filled, missing = fill_template_text(
        "Sincerely, (put your name here).", _fields()
    )
    assert "Jane Q Public" not in out
    assert MARKER in out
    assert filled == [] and missing == [NAME]


def test_email_shaped_run_collapses_to_one_address():
    """guns.lol writes XXXXX@XXXXX.XXXXX, which is one address, not three."""
    out, filled, missing = fill_template_text(
        "Email Address: XXXXX@XXXXX.XXXXX, UID: XXXXX.", _fields()
    )
    assert "jane@example.com" in out
    assert filled == [EMAIL]
    assert missing == [ACCOUNT_ID]
    assert out.count("jane@example.com") == 1


# --- classification ---------------------------------------------------------


def test_two_placeholders_of_different_kinds_in_one_body():
    """1xBet labels both slots inline, so each has to be read separately."""
    out, filled, _ = fill_template_text("Username: XXX Email: XXX", _fields())
    assert out == "Username: jqpublic Email: jane@example.com"
    assert filled == [USERNAME, EMAIL]


def test_nearest_cue_wins_so_user_name_beats_the_name_inside_it():
    body = "My full name is XXXXXX and my user name is XXXXXX."
    out, filled, _ = fill_template_text(body, _fields())
    assert out == "My full name is Jane Q Public and my user name is jqpublic."
    assert filled == [NAME, USERNAME]


def test_phone_and_signature_name_are_recognised():
    body = "Phone Number: xxxxxx. Best regards, xxxxx"
    out, filled, _ = fill_template_text(body, _fields())
    assert out == "Phone Number: +1-555-0100. Best regards, Jane Q Public"
    assert filled == [PHONE, NAME]


def test_reason_is_never_filled_even_though_it_is_recognised():
    out, filled, missing = fill_template_text(
        "I am leaving because of XXXXXX.", _fields()
    )
    assert filled == [] and missing == [REASON]
    assert "your reason for leaving" in out


def test_account_number_is_never_filled():
    for body in (
        "My customer number is XXXXXX",
        "My membership number is XXXXXX",
        "investor id: XXXXXX",
        "UID: XXXXX",
    ):
        _, filled, missing = fill_template_text(body, _fields())
        assert filled == [], body
        assert missing == [ACCOUNT_ID], body


def test_unrecognised_context_leaves_the_spot_blank():
    """Castbox says 'I use XXX to sign in'. The cue comes after, so do not guess."""
    out, filled, missing = fill_template_text("I use XXX to sign in.", _fields())
    assert filled == [] and missing == [UNKNOWN]
    assert MARKER in out


def test_french_mon_compte_is_not_guessed():
    """'faire supprimer mon compte XXX' could be a username or an email."""
    _, filled, missing = fill_template_text("faire supprimer mon compte XXX", _fields())
    assert filled == [] and missing == [UNKNOWN]


def test_german_and_spanish_cues_are_recognised():
    out, filled, _ = fill_template_text("mit der E-Mail Adresse: XXX", _fields())
    assert filled == [EMAIL] and "jane@example.com" in out
    out, filled, _ = fill_template_text("utilizando el usuario XXXXXX", _fields())
    assert filled == [USERNAME] and "jqpublic" in out


def test_classify_placeholder_reads_the_text_before_the_spot():
    body = "My username is XXXX"
    assert classify_placeholder(body, body.index("XXXX")) == USERNAME
    assert classify_placeholder("Title: XXXX", len("Title: ")) == OTHER


# --- values the user did not supply ----------------------------------------


def test_missing_username_is_marked_and_reported():
    fields = TemplateFields(name="Jane Q Public", email="jane@example.com")
    out, filled, missing = fill_template_text("My username is XXXXXX.", fields)
    assert filled == [] and missing == [USERNAME]
    assert out == "My username is <<FILL IN: your username on the service>>."


def test_empty_profile_fills_nothing_and_invents_nothing():
    fields = TemplateFields()
    out, filled, missing = fill_template_text(
        "Name: XXXX Email: XXXX Username: XXXX Phone: XXXX", fields
    )
    assert filled == []
    assert missing == [NAME, EMAIL, USERNAME, PHONE]
    assert out.count(MARKER) == 4


# --- mailto escapes ---------------------------------------------------------


def test_mailto_escapes_become_real_newlines():
    assert decode_mailto_escapes("Hello,%0D%0A%0D%0AThank you") == "Hello,\n\nThank you"
    assert decode_mailto_escapes("one%0Atwo") == "one\ntwo"


def test_body_with_escapes_renders_as_lines():
    out, _, _ = fill_template_text("My name is XXXXXX%0AMy phone is XXXXXX", _fields())
    assert out == "My name is Jane Q Public\nMy phone is +1-555-0100"


# --- the rendered message ---------------------------------------------------


def test_render_email_request_builds_a_full_message():
    rendered = render_email_request(_entry(), profile=_profile(), username="jqpublic")
    assert rendered.to == "privacy@fakebook.example"
    assert rendered.subject == "Delete my Fakebook account"
    assert rendered.from_email == "jane@example.com"
    assert rendered.body == "Please delete my account, my username is jqpublic."
    assert rendered.ready_to_send is True
    text = rendered.as_text()
    assert text.startswith("To: privacy@fakebook.example\n")
    assert "From: jane@example.com" in text
    assert "Subject: Delete my Fakebook account" in text


def test_default_subject_when_the_entry_has_none():
    rendered = render_email_request(
        _entry(email_subject=None), profile=_profile(), username="jqpublic"
    )
    assert rendered.subject == DEFAULT_SUBJECT


def test_from_email_override_picks_a_different_address():
    rendered = render_email_request(
        _entry(), profile=_profile(), username="jqpublic", from_email="jq@example.org"
    )
    assert rendered.from_email == "jq@example.org"


def test_first_profile_email_is_used_by_default():
    fields = fields_from_profile(_profile())
    assert fields.email == "jane@example.com"
    assert fields.username is None


def test_rendered_reports_missing_fields_in_plain_words():
    rendered = render_email_request(
        _entry(email_body="My username is XXXX and my reason is XXXX."),
        profile=_profile(),
    )
    assert rendered.ready_to_send is False
    lines = missing_field_lines(rendered)
    assert any("username" in line for line in lines)
    assert any("reason" in line for line in lines)


def test_subject_placeholders_are_filled_too():
    """Tragicbeautiful keeps its detail in the subject line."""
    rendered = render_email_request(
        _entry(email_subject="My phone number is XXXXXXXX", email_body="Please delete."),
        profile=_profile(),
    )
    assert rendered.subject == "My phone number is +1-555-0100"


def test_entry_without_a_body_raises():
    with pytest.raises(ValueError, match="no email template"):
        render_email_request(_entry(email_body=None), profile=_profile())


def test_has_email_template_needs_both_address_and_wording():
    assert has_email_template(_entry()) is True
    assert has_email_template(_entry(email_body=None)) is False
    assert has_email_template(_entry(email=None)) is False


def test_marker_and_labels_carry_no_dash_characters():
    """House style: no dash of any kind in prose the tool writes."""
    from erasure.legal.email_templates import LABELS, _MARKER_CLOSE, _MARKER_OPEN

    # Built from the real constants, so a future edit that adds a dash fails.
    for kind, label in LABELS.items():
        marker = _MARKER_OPEN + label + _MARKER_CLOSE
        for bad in ("-", "--", "\u2014", "\u2013"):
            assert bad not in marker, f"dash in the marker for {kind}"
    rendered = render_email_request(
        _entry(email_body="Username: XXXX Reason: XXXX UID: XXXX"),
        profile=_profile(),
    )
    for line in missing_field_lines(rendered):
        for bad in ("-", "--", "\u2014", "\u2013"):
            assert bad not in line, line


# --- the bundled dataset ----------------------------------------------------


def test_every_bundled_template_renders_without_error():
    """A wording change upstream must never crash the generator."""
    profile = _profile()
    entries = [e for e in load_directory() if has_email_template(e)]
    assert len(entries) >= 50
    for entry in entries:
        rendered = render_email_request(entry, profile=profile, username="jqpublic")
        assert rendered.to
        assert rendered.subject
        assert rendered.body


# Field words this file looks for, spelled out here rather than imported from
# the module under test. The production list can be narrowed without narrowing
# this one, which is the whole point of keeping a second copy.
_GUARD_FIELD_WORDS = (
    "email",
    "e-mail",
    "mail",
    "account",
    "username",
    "user",
    "name",
    "phone",
    "telephone",
    "address",
    "uid",
    "id",
)

# Deliberately wider than the production detector, and written independently of
# it, so that an upstream refresh introducing a blank shape the tool does not
# know about fails here instead of shipping a sample value to a real company.
#
# The first six alternatives are shapes: something around the blank marks it
# out. The last three are meaning: a token that names a field, sitting where a
# value belongs, with no delimiter of any kind. Round 2 had shapes only, and
# seven entries shipping a bare YOUR_EMAIL or LEETIFYACCOUNTID walked straight
# through it, so a guard built on delimiters is not a guard.
_WIDE_BLANK_SCAN = re.compile(
    r"'[^']{1,60}'"  # any single quoted span, which upstream uses for samples
    r"|[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"  # any address literal
    r"|\[[^\]]{1,140}\]"  # any bracket note
    r"|(?<![A-Za-z0-9])[XxYy]{2,}(?![A-Za-z0-9])"  # any letter run
    r"|<[A-Za-z][A-Za-z_]{2,30}>"  # any angle token
    r"|\((?i:put|state|insert|enter|add|include|sign|type)\b[^)]{0,90}\)"
    # any token joined by underscores, in any casing: prose never is
    r"|(?<![A-Za-z0-9_])[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+(?![A-Za-z0-9_])"
    # your, joined to a field word by nothing, a dot, an underscore or a
    # hyphen. A space makes it English ("your account"), a joiner makes it a
    # token ("your-username", "youremail", "YOUR_EMAIL").
    r"|(?<![A-Za-z0-9_])(?i:your)[._-]?(?i:" + "|".join(_GUARD_FIELD_WORDS) + r")\w*"
    # an all caps token that is a field word or ends in one
    r"|(?<![A-Za-z0-9_])[A-Z0-9]*(?:EMAIL|USERNAME|ADDRESS|ACCOUNT|PHONE|NAME|ID)"
    r"(?![A-Za-z0-9_])"
)

# Spans the wide scan flags that are genuinely literal text, not blanks. Keep
# this list tiny. A new entry here is a decision a person has to make. This is
# this file's own copy on purpose: widening the module's allow list must not
# widen this one, or a production change quietly switches the guard off.
_DELIBERATELY_LITERAL = {
    # CoinBR/Stratum decorates its subject line. The padding spaces inside the
    # brackets are what separates decoration from an instruction.
    "[ Permanently Account Deletion Request ]",
    # MEXC asks for "a photo of yourself holding your ID card".
    "ID",
    # guns.lol labels its blank "UID: XXXXX", MEXC writes "with UID #".
    "UID",
    # StreamLabs titles its email "REQUEST TO DELETE MY ACCOUNT".
    "ACCOUNT",
}


def test_no_bundled_template_leaks_any_blank_shape():
    """Every blank is either filled with a real value or visibly marked.

    This is the guard that finding 1 slipped past: three entries shipped
    'your.mail@address.tld' and 'Firstname Lastname' as ordinary prose and the
    old narrow regex only looked for XXX runs.
    """
    profile = _profile()
    marker = re.compile(r"<<FILL IN: [^>]*>>")
    filled_values = {profile.name, profile.emails[0], profile.phones[0], "jqpublic"}
    for entry in load_directory():
        if not has_email_template(entry):
            continue
        rendered = render_email_request(entry, profile=profile, username="jqpublic")
        for where, text in (("subject", rendered.subject), ("body", rendered.body)):
            stripped = marker.sub("", text)
            for hit in _WIDE_BLANK_SCAN.findall(stripped):
                if hit in _DELIBERATELY_LITERAL or hit in filled_values:
                    continue
                raise AssertionError(
                    f"{entry.name} {where} still contains an unhandled blank: {hit!r}"
                )


def test_every_span_the_tool_calls_a_blank_is_recognised_independently():
    """The converse of the scan above, and the direction it cannot see.

    The stripped scan finds a blank the tool missed. It cannot find a blank the
    tool invented: a marker is removed before the scan runs, and a filled value
    is skipped by name, so a false blank and a false fill both come back clean.
    This walks the production pattern over the raw template instead and asserts
    that the independent scan agrees each span it acts on really is a blank. A
    span the tool acts on that the wide scan does not recognise is either a
    false blank or, worse, a value about to be pasted over ordinary prose.
    """
    for entry in load_directory():
        if not has_email_template(entry):
            continue
        fields = (("subject", entry.email_subject or ""), ("body", entry.email_body or ""))
        for where, raw in fields:
            text = decode_mailto_escapes(raw)
            for match in _PLACEHOLDER_RE.finditer(text):
                span = match.group(0)
                if span in _DELIBERATELY_LITERAL:
                    continue
                assert _WIDE_BLANK_SCAN.search(span), (
                    f"{entry.name} {where}: the tool treats {span!r} as a blank "
                    "but an independent reading does not see one there"
                )


def test_ready_to_send_agrees_with_an_independent_scan():
    """ready_to_send must never be True while a blank shape survives.

    Checked against the wide scan rather than against the tool's own detector,
    so the two cannot agree by sharing the same mistake.
    """
    profile = _profile()
    marker = re.compile(r"<<FILL IN: [^>]*>>")
    filled_values = {profile.name, profile.emails[0], profile.phones[0], "jqpublic"}
    for entry in load_directory():
        if not has_email_template(entry):
            continue
        rendered = render_email_request(entry, profile=profile, username="jqpublic")
        text = marker.sub("", rendered.subject + "\n" + rendered.body)
        survivors = [
            h
            for h in _WIDE_BLANK_SCAN.findall(text)
            if h not in _DELIBERATELY_LITERAL and h not in filled_values
        ]
        if rendered.ready_to_send:
            assert not survivors, f"{entry.name} claims complete but holds {survivors}"


# --- the CLI ----------------------------------------------------------------


@pytest.fixture
def fake_setup(tmp_path):
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "name": "Jane Q Public",
                "emails": ["jane@example.com"],
                "phones": ["+1-555-0100"],
            }
        )
    )
    directory = tmp_path / "directory.json"
    directory.write_text(
        json.dumps(
            {
                "count": 3,
                "services": [
                    {
                        "name": "Fakebook",
                        "domains": ["fakebook.example"],
                        "difficulty": "hard",
                        "email": "privacy@fakebook.example",
                        "email_subject": "Delete my Fakebook account",
                        "email_body": (
                            "My full name is XXXXXX, my username is XXXXXX. "
                            "I am leaving because of XXXXXX."
                        ),
                    },
                    {
                        "name": "Addressonly",
                        "domains": ["addressonly.example"],
                        "difficulty": "limited",
                        "email": "support@addressonly.example",
                    },
                    {
                        "name": "Linkonly",
                        "domains": ["linkonly.example"],
                        "difficulty": "easy",
                        "url": "https://linkonly.example/delete",
                    },
                ],
            }
        )
    )
    return profile, directory


def _run(runner, profile, directory, *extra):
    return runner.invoke(
        cli,
        [
            "legal",
            "request",
            "--profile",
            str(profile),
            "--directory",
            str(directory),
            *extra,
        ],
    )


def test_cli_service_with_template_fills_and_reports(fake_setup):
    profile, directory = fake_setup
    result = _run(
        CliRunner(), profile, directory, "--service", "Fakebook", "--username", "jqpublic"
    )
    assert result.exit_code == 0
    assert "To: privacy@fakebook.example" in result.output
    assert "From: jane@example.com" in result.output
    assert "Jane Q Public" in result.output
    assert "jqpublic" in result.output
    assert "reason for leaving" in result.output


def test_cli_service_without_username_says_which_field_is_missing(fake_setup):
    profile, directory = fake_setup
    result = _run(CliRunner(), profile, directory, "--service", "Fakebook")
    assert result.exit_code == 0
    assert "Still to fill in yourself" in result.output
    assert "username" in result.output
    assert "--username" in result.output


def test_cli_service_with_address_but_no_wording_uses_the_letter(fake_setup):
    profile, directory = fake_setup
    result = _run(
        CliRunner(), profile, directory, "--service", "Addressonly", "--jurisdiction", "gdpr"
    )
    assert result.exit_code == 0
    assert "To: support@addressonly.example" in result.output
    assert "Article 17" in result.output
    assert "ships no wording of its own" in result.output


def test_cli_service_with_no_email_points_at_the_delete_page(fake_setup):
    profile, directory = fake_setup
    result = _run(CliRunner(), profile, directory, "--service", "Linkonly")
    assert result.exit_code == 0
    assert "https://linkonly.example/delete" in result.output
    assert "no deletion email in the directory" in result.output


def test_cli_unknown_service_exits_nonzero(fake_setup):
    profile, directory = fake_setup
    result = _run(CliRunner(), profile, directory, "--service", "NotAThing")
    assert result.exit_code == 1
    assert "No directory entry matches" in result.output


def test_cli_without_service_still_writes_a_plain_letter(fake_setup):
    profile, directory = fake_setup
    result = _run(CliRunner(), profile, directory, "--recipient", "Spokeo")
    assert result.exit_code == 0
    assert "Spokeo" in result.output
    assert "1798.105" in result.output
    assert "To: privacy@fakebook.example" not in result.output


def test_cli_saves_the_email_to_a_file(fake_setup, tmp_path):
    profile, directory = fake_setup
    out = tmp_path / "letter.txt"
    result = _run(
        CliRunner(),
        profile,
        directory,
        "--service",
        "Fakebook",
        "--username",
        "jqpublic",
        "--output",
        str(out),
    )
    assert result.exit_code == 0
    saved = out.read_text(encoding="utf-8")
    assert saved.startswith("To: privacy@fakebook.example")
    assert "jqpublic" in saved


def test_deletion_links_marks_rows_that_ship_a_template(fake_setup, tmp_path):
    profile, directory = fake_setup
    manifest = tmp_path / "accounts.json"
    manifest.write_text(
        json.dumps(
            {
                "username": "jqpublic",
                "found_count": 2,
                "hits": [
                    {"site": "Fakebook", "url": "https://fakebook.example/jqpublic"},
                    {"site": "Addressonly", "url": "https://addressonly.example/jqpublic"},
                ],
            }
        )
    )
    result = CliRunner().invoke(
        cli,
        [
            "accounts",
            "deletion-links",
            "--manifest",
            str(manifest),
            "--no-emails",
            "--directory",
            str(directory),
        ],
    )
    assert result.exit_code == 0
    assert "Email template available" in result.output
    assert "1 site(s) ship the exact wording" in result.output


def test_cli_service_accepts_a_domain_as_well_as_a_name(fake_setup):
    """An emails manifest gives domains, so --service fakebook.example must work."""
    profile, directory = fake_setup
    result = _run(
        CliRunner(),
        profile,
        directory,
        "--service",
        "fakebook.example",
        "--username",
        "jqpublic",
    )
    assert result.exit_code == 0
    assert "Matched directory entry: Fakebook" in result.output
    assert "To: privacy@fakebook.example" in result.output


# --- finding 1: literal sample values read like ordinary prose --------------


def test_quoted_sample_email_is_treated_as_a_blank():
    """Check24 ships 'your.mail@address.tld'. It is a slot, not the user's address."""
    out, filled, missing = fill_template_text(
        "Die betreffende E-Mail-Adresse lautet: 'your.mail@address.tld'", _fields()
    )
    assert "address.tld" not in out
    assert "jane@example.com" in out
    assert filled == [EMAIL] and missing == []


def test_quoted_sample_name_is_treated_as_a_blank():
    out, filled, _ = fill_template_text("Mit freundlichen Grüßen 'Your name'", _fields())
    assert out == "Mit freundlichen Grüßen Jane Q Public"
    assert filled == [NAME]


def test_quoted_firstname_lastname_is_treated_as_a_blank():
    """Momox ships 'Firstname Lastname' with no XXX run anywhere."""
    out, filled, _ = fill_template_text("mit freundlichen Grüßen, 'Firstname Lastname'", _fields())
    assert "Firstname" not in out and "Lastname" not in out
    assert "Jane Q Public" in out
    assert filled == [NAME]


def test_quoted_sample_username_is_treated_as_a_blank():
    """PythonAnywhere ships 'your-username' in both the subject and the body."""
    out, filled, _ = fill_template_text("delete my account 'your-username' now", _fields())
    assert out == "delete my account jqpublic now"
    assert filled == [USERNAME]


def test_sample_value_is_marked_when_the_user_has_no_value_for_it():
    out, filled, missing = fill_template_text(
        "Adresse lautet: 'your.mail@address.tld'", TemplateFields()
    )
    assert "address.tld" not in out
    assert MARKER in out
    assert filled == [] and missing == [EMAIL]


def test_unquoted_sample_address_is_treated_as_a_blank():
    out, filled, _ = fill_template_text("My address is your.name@sample.tld here", _fields())
    assert "your.name@sample.tld" not in out
    assert out == "My address is jane@example.com here"
    assert filled == [EMAIL]


def test_sentence_case_bracket_instruction_is_a_blank():
    """Stardock ships [Give details of what personal data you want erased/deleted.]."""
    out, filled, missing = fill_template_text(
        "I wish to exercise my right to erasure.\n\n"
        "[Give details of what personal data you want erased/deleted.]",
        _fields(),
    )
    assert "Give details" not in out
    assert MARKER in out
    assert filled == [] and missing == [OTHER]


def test_padded_bracket_decoration_is_still_left_alone():
    """The padding spaces are what separate decoration from an instruction."""
    out, _, missing = fill_template_text("[ Permanently Account Deletion Request ]", _fields())
    assert out == "[ Permanently Account Deletion Request ]"
    assert missing == []


def test_real_bundled_entries_with_sample_values_are_handled():
    """The four dataset entries that carry sample values rather than XXX runs."""
    profile = _profile()
    by_name = {e.name: e for e in load_directory()}
    for name in ("Check24 Deutschland", "Momox Fashion", "PythonAnywhere"):
        rendered = render_email_request(by_name[name], profile=profile, username="jqpublic")
        whole = rendered.subject + rendered.body
        for sample in ("address.tld", "address.here", "your-username", "Firstname Lastname"):
            assert sample not in whole, f"{name} still ships {sample}"
    check24 = render_email_request(
        by_name["Check24 Deutschland"], profile=profile, username="jqpublic"
    )
    assert "jane@example.com" in check24.body
    assert "Jane Q Public" in check24.body
    stardock = render_email_request(by_name["Stardock"], profile=profile, username="jqpublic")
    assert stardock.ready_to_send is False
    assert MARKER in stardock.body


# --- finding 2: a blank must not inherit the previous blank's cue -----------


def test_second_blank_does_not_inherit_the_first_blanks_kind():
    out, filled, missing = fill_template_text(
        "My email is XXXX and my account number is XXXX.", _fields()
    )
    assert out.count("jane@example.com") == 1
    assert out.endswith("<<FILL IN: a detail this service asks for>>.")
    assert filled == [EMAIL] and missing == [UNKNOWN]


def test_phone_does_not_bleed_into_date_of_birth():
    out, filled, missing = fill_template_text(
        "My phone number is XXXX and my date of birth is XXXX.", _fields()
    )
    assert out.count("+1-555-0100") == 1
    assert filled == [PHONE] and missing == [UNKNOWN]


def test_username_does_not_bleed_into_order_reference():
    out, filled, missing = fill_template_text(
        "My username is XXXX, my order reference is XXXX.", _fields()
    )
    assert out.count("jqpublic") == 1
    assert filled == [USERNAME] and missing == [UNKNOWN]


def test_name_compounds_are_not_filled_with_the_legal_name():
    """A display name or a surname is not the full name on the account."""
    for body in (
        "My display name is XXXX",
        "My screen name is XXXX",
        "My first name is XXXX",
        "My last name is XXXX",
        "My surname is XXXX",
    ):
        out, filled, missing = fill_template_text(body, _fields())
        assert filled == [], body
        assert missing == [UNKNOWN], body
        assert "Jane Q Public" not in out, body


def test_full_name_still_fills_after_the_compound_cues_were_added():
    out, filled, _ = fill_template_text("My full name is XXXX", _fields())
    assert out == "My full name is Jane Q Public"
    assert filled == [NAME]


# --- finding 5: an ambiguous label stays blank ------------------------------


def test_account_name_is_ambiguous_and_stays_blank():
    """Could be a handle or a display name, so by the module's own rule, neither."""
    out, filled, missing = fill_template_text("Account Name: XXXX", _fields())
    assert filled == [] and missing == [UNKNOWN]
    assert "jqpublic" not in out and "Jane Q Public" not in out


# --- finding 7: the report counts spots, not kinds --------------------------


def test_every_blank_spot_is_listed_with_its_position():
    rendered = render_email_request(
        _entry(email_body="First: [SOMETHING A] then second: [SOMETHING B]"),
        profile=_profile(),
    )
    lines = missing_field_lines(rendered)
    assert len(lines) == 2
    assert "blank 1 in the body" in lines[0]
    assert "blank 2 in the body" in lines[1]


def test_subject_and_body_blanks_are_reported_separately():
    rendered = render_email_request(
        _entry(email_subject="Reference [SOME REF]", email_body="Reason: XXXX"),
        profile=_profile(),
    )
    wheres = {b.where for b in rendered.blanks}
    assert wheres == {"subject", "body"}
    assert len(rendered.blanks) == 2


# --- finding 3: the service argument is text a person typed -----------------


def test_cli_service_with_a_bracket_does_not_traceback(fake_setup):
    """A stray bracket used to reach urlsplit and raise Invalid IPv6 URL."""
    profile, directory = fake_setup
    result = _run(CliRunner(), profile, directory, "--service", "foo[bar")
    assert result.exit_code == 1
    assert "No directory entry matches" in result.output
    assert "Traceback" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_cli_service_with_other_junk_is_reported_not_raised(fake_setup):
    profile, directory = fake_setup
    for junk in ("http://[", "a]b", "://"):
        result = _run(CliRunner(), profile, directory, "--service", junk)
        assert result.exit_code == 1, junk
        assert "No directory entry matches" in result.output, junk


# --- finding 4: two entries can claim one domain ----------------------------


def test_domain_tie_prefers_the_entry_that_ships_a_template():
    """Pix and Pix fr both claim pix.fr. Only Pix fr can actually be emailed."""
    directory = load_directory()
    matched = match_entry("pix.fr", "pix.fr", directory)
    assert matched is not None
    assert matched.name == "Pix fr"
    assert matched.email == "dpd@pix.fr"
    assert has_email_template(matched)


def test_domain_tie_break_prefers_an_address_over_nothing():
    plain = DeletionEntry(name="Alpha", domains=["tie.example"], difficulty="easy")
    with_mail = DeletionEntry(
        name="Beta", domains=["tie.example"], difficulty="hard", email="p@tie.example"
    )
    assert match_entry("x", "tie.example", [plain, with_mail]).name == "Beta"
    # Order in the directory must not decide it.
    assert match_entry("x", "tie.example", [with_mail, plain]).name == "Beta"


def test_a_zero_score_entry_never_wins_on_the_tie_break():
    """The tie break ranks matches, it must not invent one."""
    directory = [
        DeletionEntry(
            name="Unrelated",
            domains=["unrelated.example"],
            difficulty="hard",
            email="a@unrelated.example",
            email_body="Please delete.",
        )
    ]
    assert match_entry("nothing-like-it", "nothing-like-it", directory) is None


@pytest.fixture
def twin_setup(tmp_path):
    """Two entries claiming one domain, contacted in two different places."""
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"name": "Jane Q Public", "emails": ["jane@example.com"]}))
    directory = tmp_path / "directory.json"
    directory.write_text(
        json.dumps(
            {
                "count": 2,
                "services": [
                    {
                        "name": "Twin A",
                        "domains": ["twin.example"],
                        "difficulty": "easy",
                        "url": "https://twin.example/delete",
                    },
                    {
                        "name": "Twin B",
                        "domains": ["twin.example"],
                        "difficulty": "hard",
                        "email": "p@twin.example",
                        "email_body": "Please delete my account.",
                    },
                ],
            }
        )
    )
    return profile, directory


def test_cli_says_when_another_entry_shares_the_domain(twin_setup):
    """Asked for by name, the note still points at the other entry."""
    profile, directory = twin_setup
    result = _run(CliRunner(), profile, directory, "--service", "Twin B")
    assert result.exit_code == 0
    assert "Matched directory entry: Twin B" in result.output
    assert "Also listing a domain of Twin B: Twin A" in result.output


# --- finding 9: the summary counts services, not hits -----------------------


def test_deletion_links_counts_a_repeated_service_once(fake_setup, tmp_path):
    profile, directory = fake_setup
    manifest = tmp_path / "accounts.json"
    manifest.write_text(
        json.dumps(
            {
                "username": "jqpublic",
                "found_count": 2,
                "hits": [
                    {"site": "Fakebook", "url": "https://fakebook.example/jqpublic"},
                    {"site": "Fakebook", "url": "https://fakebook.example/other"},
                ],
            }
        )
    )
    result = CliRunner().invoke(
        cli,
        [
            "accounts",
            "deletion-links",
            "--manifest",
            str(manifest),
            "--no-emails",
            "--directory",
            str(directory),
        ],
    )
    assert result.exit_code == 0
    assert "1 site(s) ship the exact wording" in result.output
    # The command it prints has to work against the same directory.
    assert "--directory" in result.output


# --- finding 10: paths the lead named but nothing exercised -----------------


def test_cli_save_writes_the_email_under_state(fake_setup, tmp_path, monkeypatch):
    profile, directory = fake_setup
    monkeypatch.chdir(tmp_path)
    result = _run(
        CliRunner(), profile, directory, "--service", "Fakebook", "--username", "jqpublic", "--save"
    )
    assert result.exit_code == 0
    saved = list((tmp_path / "state" / "legal").glob("*.txt"))
    assert len(saved) == 1
    text = saved[0].read_text(encoding="utf-8")
    assert text.startswith("To: privacy@fakebook.example")
    assert saved[0].name.startswith("email_")


def test_cli_save_still_works_for_a_plain_letter(fake_setup, tmp_path, monkeypatch):
    profile, directory = fake_setup
    monkeypatch.chdir(tmp_path)
    result = _run(CliRunner(), profile, directory, "--recipient", "Spokeo", "--save")
    assert result.exit_code == 0
    saved = list((tmp_path / "state" / "legal").glob("*.txt"))
    assert len(saved) == 1
    assert saved[0].name.startswith("ccpa_spokeo")


def test_jurisdiction_is_ignored_on_the_template_path(fake_setup):
    """The dataset wording is what the service asks for, so no statute is cited."""
    profile, directory = fake_setup
    result = _run(
        CliRunner(),
        profile,
        directory,
        "--service",
        "Fakebook",
        "--username",
        "jqpublic",
        "--jurisdiction",
        "gdpr",
    )
    assert result.exit_code == 0
    assert "Article 17" not in result.output
    assert "To: privacy@fakebook.example" in result.output


def test_jurisdiction_is_still_used_when_there_is_no_template(fake_setup):
    profile, directory = fake_setup
    result = _run(
        CliRunner(), profile, directory, "--service", "Addressonly", "--jurisdiction", "gdpr"
    )
    assert result.exit_code == 0
    assert "Article 17" in result.output


# --- round 3, finding 1: blanks written as bare undelimited tokens ----------


def test_screaming_snake_token_is_marked_and_never_filled():
    """Found, labelled and handed back to the user, not guessed at."""
    out, filled, missing = fill_template_text(
        "Please delete the account for YOUR_EMAIL belonging to FULL_NAME.", _fields()
    )
    assert filled == []
    assert missing == [EMAIL, NAME]
    assert out == (
        "Please delete the account for <<FILL IN: your email address>> "
        "belonging to <<FILL IN: your full name>>."
    )


def test_screaming_snake_account_token_is_marked_not_filled():
    """An account identifier is never guessed, whatever the profile holds."""
    out, filled, missing = fill_template_text("Delete YOUR_ACCOUNT please.", _fields())
    assert missing == [ACCOUNT_ID]
    assert filled == []
    assert "<<FILL IN: an account, customer or reference number>>" in out


def test_bare_caps_token_without_an_underscore_is_caught():
    """Leetify runs its field names together, so an underscore rule misses it."""
    out, filled, missing = fill_template_text(
        "My address is LEETIFYEMAILADDRESS and my ID is LEETIFYACCOUNTID.", _fields()
    )
    assert filled == []
    assert missing == [EMAIL, ACCOUNT_ID]
    assert "LEETIFY" not in out
    assert out.count(MARKER) == 2


def test_a_bare_token_is_never_filled_however_it_reads():
    """A word can end in a field word and still be ordinary prose.

    This is the reason bare tokens are marked rather than read. Filling any of
    these would paste the user's legal name or phone number over a real word
    and still report the letter complete.
    """
    cases = {
        "PLEASE CONFIRM SURNAME NOW.": NAME,
        "PLEASE CONFIRM IPHONE NOW.": PHONE,
        "NICKNAME": NAME,
        "HOSTNAME": NAME,
        "DEVICE_NAME": NAME,
        "PHONE_MODEL": PHONE,
    }
    for text, kind in cases.items():
        out, filled, missing = fill_template_text(text, _fields())
        assert filled == [], text
        assert missing == [kind], text
        assert MARKER in out, text
        for value in ("Jane Q Public", "jane@example.com", "+1-555-0100", "jqpublic"):
            assert value not in out, f"{text} leaked {value}"


def test_a_delimited_token_still_fills():
    """The fix withholds the bare shapes only. A delimiter says it is a blank."""
    for text in (
        "Delete the account for <YOUR_EMAIL>, thanks.",
        "Die E-Mail-Adresse lautet: 'your.mail@address.tld'",
        "Write to me at your-email@address.here please.",
    ):
        out, filled, missing = fill_template_text(text, _fields())
        assert filled == [EMAIL], text
        assert missing == [], text
        assert "jane@example.com" in out, text


def test_all_caps_prose_is_left_alone():
    """Real words in a caps subject must not be mistaken for field names."""
    for prose in (
        "PERSONAL DATA.",  # Basilica di San Pietro subject
        "ACCESS AND CORRECT INFORMATION",  # Pixel Starships subject
        "REQUEST TO DELETE MY ACCOUNT",  # StreamLabs subject
        "Ich habe mein CHECK24-Konto geloescht.",  # Check24 brand
        "Include a photo of yourself holding your ID card.",  # MEXC
    ):
        out, filled, missing = fill_template_text(prose, _fields())
        assert out == prose, prose
        assert filled == [] and missing == [], prose


def test_a_protected_caps_word_does_not_shift_the_next_blank():
    """The allow list must not eat the cue the following blank reads.

    guns.lol writes "UID: XXXXX" and Amso "Account ID: XXXX". If UID or ID
    counted as a blank, the run after it would start its search past the cue
    and degrade from an account number to an unknown detail.
    """
    for text in ("Below are my details: UID: XXXXX.", "Account ID: XXXX, thanks."):
        _, filled, missing = fill_template_text(text, _fields())
        assert missing == [ACCOUNT_ID], text
        assert filled == [], text


def test_real_bundled_entries_with_bare_tokens_are_handled():
    """The seven dataset entries that ship a blank as a bare token.

    Looked up by name on purpose. If upstream renames or drops one this raises
    KeyError, which is the loud failure worth having.
    """
    profile = _profile()
    by_name = {e.name: e for e in load_directory()}
    tokens = {
        "Basilica di San Pietro": ("YOUR_EMAIL",),
        "Boulanger": ("YOUR_EMAIL",),
        "DFCG": ("YOUR_EMAIL",),
        "TED": ("YOUR_EMAIL",),
        "Musei Italiani": ("YOUR_ACCOUNT",),
        "VirtCloud": ("FULL_NAME", "EMAIL_ADDRESS"),
        "Leetify": ("LEETIFYEMAILADDRESS", "LEETIFYACCOUNTID"),
    }
    for name, shipped in tokens.items():
        rendered = render_email_request(by_name[name], profile=profile, username="jqpublic")
        whole = rendered.subject + rendered.body
        for token in shipped:
            assert token not in whole, f"{name} still ships {token}"
        # Every one is marked, none is filled: the token had no delimiter, so
        # reading it would be a guess.
        assert rendered.ready_to_send is False, name
        assert len(rendered.blanks) == len(shipped), name
        assert MARKER in rendered.body, name
        for value in ("Jane Q Public", "jane@example.com", "+1-555-0100", "jqpublic"):
            assert value not in whole, f"{name} filled a bare token with {value}"
    assert ACCOUNT_ID in render_email_request(
        by_name["Musei Italiani"], profile=profile
    ).missing

    # The caps prose in the same dataset survives untouched.
    basilica = render_email_request(
        by_name["Basilica di San Pietro"], profile=profile, username="jqpublic"
    )
    assert basilica.subject == "PERSONAL DATA."
    mexc = render_email_request(by_name["MEXC"], profile=profile, username="jqpublic")
    assert "your ID card" in mexc.body
    check24 = render_email_request(
        by_name["Check24 Deutschland"], profile=profile, username="jqpublic"
    )
    assert "CHECK24" in check24.body


# --- round 3, finding 3: a nickname is not a username ----------------------


def test_nickname_stays_blank():
    """A nickname is a display name on most services, not the login handle."""
    out, filled, missing = fill_template_text("My nickname is XXXX.", _fields())
    assert missing == [UNKNOWN]
    assert filled == []
    assert "jqpublic" not in out
    assert "Jane Q Public" not in out


def test_username_and_full_name_still_fill():
    """The nickname change must not take the two unambiguous cues with it."""
    out, filled, _ = fill_template_text(
        "My username is XXXX and my full name is XXXX.", _fields()
    )
    assert filled == [USERNAME, NAME]
    assert "jqpublic" in out and "Jane Q Public" in out


# --- round 3, finding 4: a domain tie asks instead of picking ---------------


def test_domain_tie_with_different_contact_paths_asks(twin_setup):
    profile, directory = twin_setup
    result = _run(CliRunner(), profile, directory, "--service", "twin.example")
    # Rich wraps the console, so compare on collapsed whitespace.
    flat = " ".join(result.output.split())
    assert result.exit_code == 1
    assert "matches 2 directory entries that are contacted in different places" in flat
    assert "Twin A: web form at https://twin.example/delete" in flat
    assert "Twin B: email to p@twin.example" in flat
    # Every candidate is offered by name, so the hint cannot steer the user
    # towards the entry that happens to sort first.
    assert "Run it again with one of those names exactly:" in flat
    assert '--service "Twin A"' in flat
    assert '--service "Twin B"' in flat
    # Nothing was rendered: no message, and none of the user's details.
    assert "To: p@twin.example" not in flat
    assert "Jane Q Public" not in flat


def test_the_exact_name_still_works_after_a_tie(twin_setup):
    profile, directory = twin_setup
    result = _run(CliRunner(), profile, directory, "--service", "Twin A")
    assert result.exit_code == 0
    assert "Matched directory entry: Twin A" in result.output


def test_domain_tie_sharing_one_address_is_still_broken_automatically(tmp_path):
    """Same address on both sides means the choice sends nothing anywhere new."""
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"name": "Jane Q Public", "emails": ["jane@example.com"]}))
    directory = tmp_path / "directory.json"
    directory.write_text(
        json.dumps(
            {
                "count": 2,
                "services": [
                    {
                        "name": "Same A",
                        "domains": ["same.example"],
                        "difficulty": "easy",
                        "email": "privacy@same.example",
                    },
                    {
                        "name": "Same B",
                        "domains": ["same.example"],
                        "difficulty": "hard",
                        "email": "privacy@same.example",
                        "email_body": "Please delete my account.",
                    },
                ],
            }
        )
    )
    result = _run(CliRunner(), profile, directory, "--service", "same.example")
    assert result.exit_code == 0
    assert "Matched directory entry: Same B" in result.output


def test_two_web_forms_are_still_broken_automatically(tmp_path):
    """Neither entry can be emailed, so no address of the user's is disclosed."""
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"name": "Jane Q Public", "emails": ["jane@example.com"]}))
    directory = tmp_path / "directory.json"
    directory.write_text(
        json.dumps(
            {
                "count": 2,
                "services": [
                    {
                        "name": "Form A",
                        "domains": ["form.example"],
                        "difficulty": "easy",
                        "url": "https://form.example/a",
                    },
                    {
                        "name": "Form B",
                        "domains": ["form.example"],
                        "difficulty": "hard",
                        "url": "https://form.example/b",
                    },
                ],
            }
        )
    )
    result = _run(CliRunner(), profile, directory, "--service", "form.example")
    assert result.exit_code == 0
    assert "Matched directory entry: Form A" in result.output


def test_a_domain_tie_writes_nothing_to_output_or_state(twin_setup, tmp_path, monkeypatch):
    """The exit has to happen before any file is written."""
    import erasure.legal.generator as generator

    profile, directory = twin_setup
    out = tmp_path / "letter.txt"
    saved = []
    monkeypatch.setattr(generator, "save_request", lambda *a, **k: saved.append(a) or "x")
    result = _run(
        CliRunner(),
        profile,
        directory,
        "--service",
        "twin.example",
        "--output",
        str(out),
        "--save",
    )
    assert result.exit_code == 1
    assert not out.exists()
    assert saved == []


def test_real_domain_ties_ask_for_the_exact_name():
    """The three shared domains in the snapshot whose entries differ."""
    directory = load_directory()
    expected = {
        "pix.fr": {"Pix", "Pix fr"},
        "trenitalia.com": {"Trenitalia", "Trenitalia France"},
        "fxhome.com": {"FXhome", "HitFilm"},
    }
    for domain, names in expected.items():
        tied = match_candidates(domain, domain, directory)
        assert {e.name for e in tied} == names, domain
        assert len({e.email for e in tied}) > 1, domain


def test_entry_names_that_could_tie_still_resolve_to_themselves():
    """Asking by name must never become ambiguous.

    Only an entry that shares a domain with another, or whose name reads as a
    host, can tie with anything, so those are the names checked here. The whole
    set of 2,612 was swept once by hand and every name resolved to itself; this
    keeps the part of it that can actually break, because sweeping all 2,612
    takes about four minutes.
    """
    directory = load_directory()
    claimed = {}
    for entry in directory:
        for domain in entry.domains:
            claimed.setdefault(domain.lower(), []).append(entry.name)
    shared = {d for d, names in claimed.items() if len(names) > 1}

    def name_reads_as_another_entrys_domain(entry):
        host = _host(entry.name.strip().lower())
        if not host:
            return False
        return any(
            (host == domain or host.endswith("." + domain))
            and any(owner != entry.name for owner in owners)
            for domain, owners in claimed.items()
        )

    risky = [
        e
        for e in directory
        if any(d.lower() in shared for d in e.domains)
        or name_reads_as_another_entrys_domain(e)
    ]
    assert len(risky) >= 30
    for entry in risky:
        tied = match_candidates(entry.name, entry.name, directory)
        assert match_entry(entry.name, entry.name, directory).name == entry.name, entry.name
        assert not (len(tied) > 1 and len({e.email for e in tied}) > 1), entry.name


def test_match_entry_keeps_its_silent_tie_break_for_the_hit_list():
    """`accounts deletion-links` cannot ask, so its matcher still picks one."""
    plain = DeletionEntry(name="Alpha", domains=["tie.example"], difficulty="easy")
    with_mail = DeletionEntry(
        name="Beta", domains=["tie.example"], difficulty="hard", email="p@tie.example"
    )
    assert match_entry("x", "tie.example", [plain, with_mail]).name == "Beta"
    assert [e.name for e in match_candidates("x", "tie.example", [plain, with_mail])] == [
        "Alpha",
        "Beta",
    ]
