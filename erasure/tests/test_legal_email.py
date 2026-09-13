"""Tests for filling the deletion email templates that ship with the directory.

Every test builds its own fake profile and its own fake directory entries. The
one test that touches the bundled dataset only checks that it renders, so a
refresh from upstream cannot turn a wording change into a failing assertion.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from erasure.accounts.justdelete import DeletionEntry, load_directory
from erasure.cli import cli
from erasure.legal.email_templates import (
    ACCOUNT_ID,
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
    rendered = render_email_request(
        _entry(email_body="Username: XXXX Reason: XXXX UID: XXXX"),
        profile=_profile(),
    )
    prose = " ".join(missing_field_lines(rendered))
    for bad in ("--", "—", "–"):
        assert bad not in prose
    # The markers themselves are prose too.
    for bad in ("-", "—", "–"):
        assert bad not in "<<FILL IN: your username on the service>>"


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


def test_no_bundled_template_leaks_an_unfilled_x_run():
    """Every placeholder is either filled or replaced by a visible marker."""
    import re

    profile = _profile()
    leftover = re.compile(r"(?<![A-Za-z0-9])(?:[Xx]{3,}|[Yy]{3,})(?![A-Za-z0-9])")
    for entry in load_directory():
        if not has_email_template(entry):
            continue
        rendered = render_email_request(entry, profile=profile, username="jqpublic")
        assert not leftover.search(rendered.body), entry.name
        assert not leftover.search(rendered.subject), entry.name


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
