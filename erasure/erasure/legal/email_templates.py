"""Fill the deletion email templates that ship with the JustDeleteMe directory.

Some services will not delete an account from a settings page at all. They only
act on an email, and upstream ships the wording they expect. This module turns
one of those directory entries plus the user's own details into a message that
is ready to send.

The dataset does not use named tokens. Placeholders are written by hand by the
contributor who documented the service, so they take several shapes: ``XXXXXX``
runs, ``<YOUR_EMAIL>``, a bracket note such as ``[NUMBER OR 0]``, a
parenthetical instruction such as ``(put your name here)``, and, easiest to
miss, a literal sample value such as ``'your.mail@address.tld'`` or
``'Firstname Lastname'`` that reads like real text. There is no token
vocabulary to look up, so each blank is classified by the words that come
immediately before it, and a value is filled in only when that reading is
unambiguous and the user actually supplied the value.

Anything else is left in place as a visible marker and reported in
``RenderedEmail.blanks``. Nothing is ever guessed. A wrong username in a
deletion request is worse than a blank the user fills in themselves, and a
sample address left in place is worse still, because the request cannot
succeed and the user has no way to tell.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from erasure.accounts.justdelete import DeletionEntry
from erasure.profile import UserProfile

# Subject used when a directory entry gives an address but no subject line.
# Matches the wording `erasure accounts deletion-links` already prints.
DEFAULT_SUBJECT = "Account Deletion Request"

# Field kinds a blank can stand for.
EMAIL = "email"
USERNAME = "username"
NAME = "name"
PHONE = "phone"
ACCOUNT_ID = "account_id"
REASON = "reason"
OTHER = "other"
UNKNOWN = "unknown"

# Only these four can be answered from a profile plus the command options.
# An account number, a reason for leaving, a passport and anything unrecognised
# are always left for the user, even when the profile happens to hold something
# that looks similar.
FILLABLE = (EMAIL, USERNAME, NAME, PHONE)

# What to call each kind when telling the user what is still blank.
LABELS = {
    EMAIL: "your email address",
    USERNAME: "your username on the service",
    NAME: "your full name",
    PHONE: "your phone number",
    ACCOUNT_ID: "an account, customer or reference number",
    REASON: "your reason for leaving",
    OTHER: "a detail this service asks for",
    UNKNOWN: "a detail this service asks for",
}

# Markers are wrapped in angle brackets, not square brackets, so that Rich
# never reads them as console markup when the letter is printed.
_MARKER_OPEN = "<<FILL IN: "
_MARKER_CLOSE = ">>"

# Blank shapes actually present in the dataset. Order inside the pattern
# matters, widest first: a quoted sample has to win over the bare email inside
# it, and the email shaped run has to win over the plain run so that
# ``XXXXX@XXXXX.XXXXX`` counts as one address and not three fragments.
_PLACEHOLDER_RE = re.compile(
    # 'your.mail@address.tld', 'Your name', 'Firstname Lastname', 'your-username'
    r"(?P<quoted_sample>'(?i:your[^']{0,60}|firstname\s+lastname|first\s+last"
    r"|full\s+name|name\s+here)')"
    # A sample address written without quotes.
    r"|(?P<sample_email>[A-Za-z0-9._%+\-]+@(?:[A-Za-z0-9.\-]+\."
    r"(?i:tld|here|invalid|test|example|localhost)"
    r"|(?i:address|example|domain|yourdomain|mydomain)\.[A-Za-z]{2,6}))"
    r"|(?<![A-Za-z0-9])(?P<email_shaped>[Xx]{2,}@[Xx]{2,}\.[Xx]{2,})(?![A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])(?P<run>[Xx]{2,}|[Yy]{3,})(?![A-Za-z0-9])"
    r"|(?P<angle><[A-Za-z][A-Za-z_]{2,30}>)"
    r"|(?P<paren>\((?i:put|state|insert|enter|add|include|sign|type)\b[^)]{0,90}\))"
    # A bracket note, either an instruction or anything without padding spaces.
    # Padding marks decoration: CoinBR titles its subject
    # "[ Permanently Account Deletion Request ]" and that is not a blank.
    r"|(?P<bracket>\[\s*(?i:give|enter|insert|state|put|add|include|describe"
    r"|specify|provide|fill|type)\b[^\]]{0,140}\]"
    r"|\[(?!\s)[^\]]{1,140}(?<!\s)\])"
)

# Shapes that are instructions written for a person to read and act on. They
# are labelled so the report says what is being asked for, but never filled.
_NEVER_FILLED_GROUPS = ("paren", "bracket")

# How much text before a blank is read when deciding what it stands for.
_CONTEXT_CHARS = 70

# Literal cues, matched against the lowercased text just before a blank. The
# cue that ends nearest the blank wins, and on a tie the longer cue wins, so
# "user name" beats the bare "name" inside it. Cues mapped to UNKNOWN exist to
# beat a shorter cue that would otherwise fill the wrong thing: "display name"
# is not a full legal name, and "Account Name" could be either a handle or a
# display name, so both stay blank.
_CUES: tuple[tuple[str, str], ...] = (
    ("name", NAME),
    ("full name", NAME),
    ("best regards", NAME),
    ("kind regards", NAME),
    ("regards,", NAME),
    ("sincerely", NAME),
    ("nombre", NAME),
    ("user name", USERNAME),
    ("username", USERNAME),
    ("nickname", USERNAME),
    ("usuario", USERNAME),
    ("login", USERNAME),
    ("account name", UNKNOWN),
    ("display name", UNKNOWN),
    ("screen name", UNKNOWN),
    ("first name", UNKNOWN),
    ("last name", UNKNOWN),
    ("surname", UNKNOWN),
    ("email", EMAIL),
    ("e-mail", EMAIL),
    ("email address", EMAIL),
    ("e-mail address", EMAIL),
    ("mail adresse", EMAIL),
    ("correo", EMAIL),
    ("phone", PHONE),
    ("phone number", PHONE),
    ("telephone", PHONE),
    ("mobile number", PHONE),
    ("reason", REASON),
    ("because", REASON),
    ("because of", REASON),
    ("account id", ACCOUNT_ID),
    ("uid", ACCOUNT_ID),
    ("customer number", ACCOUNT_ID),
    ("membership number", ACCOUNT_ID),
    ("investor id", ACCOUNT_ID),
    ("wu number", ACCOUNT_ID),
    ("passport", ACCOUNT_ID),
    ("title", OTHER),
)

# Words that name a field when they appear inside the blank itself, such as
# <YOUR_EMAIL> or [NUMBER OR 0]. Checked in order, first hit wins.
_TOKEN_WORDS: tuple[tuple[str, str], ...] = (
    (r"mail", EMAIL),
    (r"user", USERNAME),
    (r"reason", REASON),
    (r"name", NAME),
    (r"phone|telephone|mobile", PHONE),
    (r"\buid\b|\bid\b|number|reference", ACCOUNT_ID),
)


@dataclass(frozen=True)
class Blank:
    """One spot the user still has to complete, and where it sits."""

    kind: str
    where: str  # "subject" or "body"
    index: int  # 1 based, counting blanks within that field

    @property
    def label(self) -> str:
        return LABELS[self.kind]

    def describe(self) -> str:
        return f"{self.label} (blank {self.index} in the {self.where})"


@dataclass(frozen=True)
class RenderedEmail:
    """A deletion email built from a directory entry and the user's details."""

    service: str
    to: str
    subject: str
    body: str
    from_email: Optional[str] = None
    blanks: tuple[Blank, ...] = ()
    filled: tuple[str, ...] = ()

    @property
    def missing(self) -> tuple[str, ...]:
        """The kind of every spot still blank, one entry per spot."""
        return tuple(b.kind for b in self.blanks)

    @property
    def ready_to_send(self) -> bool:
        """True when no blank was left for the user to complete."""
        return not self.blanks

    def as_text(self) -> str:
        """The whole message as one block the user can copy into a mail client."""
        lines = [f"To: {self.to}"]
        if self.from_email:
            lines.append(f"From: {self.from_email}")
        lines.append(f"Subject: {self.subject}")
        lines.append("")
        lines.append(self.body)
        return "\n".join(lines)


@dataclass
class TemplateFields:
    """The values a template can be filled from."""

    name: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None

    def value_for(self, kind: str) -> Optional[str]:
        return {
            NAME: self.name,
            EMAIL: self.email,
            USERNAME: self.username,
            PHONE: self.phone,
        }.get(kind)


def fields_from_profile(
    profile: UserProfile,
    *,
    username: Optional[str] = None,
    from_email: Optional[str] = None,
) -> TemplateFields:
    """Build the fillable values from a profile plus anything passed by hand.

    The profile has no username, so a username only ever comes from the caller.
    When the profile lists several addresses the first is used unless the caller
    names one, and the command prints which address it picked.
    """
    chosen_email = from_email or (profile.emails[0] if profile.emails else None)
    return TemplateFields(
        name=profile.name or None,
        email=chosen_email,
        username=username,
        phone=profile.phones[0] if profile.phones else None,
    )


def decode_mailto_escapes(text: str) -> str:
    """Turn the percent escapes a few upstream bodies carry into real newlines.

    Those entries were written as mailto links, so their line breaks survive in
    the dataset as ``%0D%0A``. Only the two newline escapes are touched, because
    those are the only percent sequences the dataset contains.
    """
    return text.replace("%0D%0A", "\n").replace("%0A", "\n").replace("%0D", "\n")


def classify_token_text(token: str) -> str:
    """Read a blank that names its own field, such as ``<YOUR_EMAIL>``.

    Also used to label a bracket note, a parenthetical instruction and a quoted
    sample value, so the report can say what is being asked for.
    """
    inner = token.strip("<>()[]'\" ").lower()
    # An address is an address even when its local part spells another field,
    # as in 'your.name@example.com'.
    if "@" in inner:
        return EMAIL
    for pattern, kind in _TOKEN_WORDS:
        if re.search(pattern, inner):
            return kind
    return OTHER


def classify_placeholder(text: str, start: int, floor: int = 0) -> str:
    """Decide what the blank at ``start`` stands for, from the words before it.

    ``floor`` is where the previous blank ended. The search never reads past it,
    so a blank with no cue of its own cannot inherit the previous blank's kind.
    Returns UNKNOWN when no cue is close enough to be sure, which keeps the spot
    blank rather than filling it with the wrong thing.
    """
    lower = max(0, start - _CONTEXT_CHARS, floor)
    context = text[lower:start].lower()
    best_kind = UNKNOWN
    best_end = -1
    best_len = -1
    for cue, kind in _CUES:
        pos = context.rfind(cue)
        if pos == -1:
            continue
        end = pos + len(cue)
        if end > best_end or (end == best_end and len(cue) > best_len):
            best_end = end
            best_len = len(cue)
            best_kind = kind
    return best_kind


def fill_template_text(text: str, fields: TemplateFields) -> tuple[str, list[str], list[str]]:
    """Fill every blank in ``text`` that can be filled safely.

    Returns the filled text, the kinds that were filled, and the kinds that were
    left blank, one entry per spot in both lists. Blanks are replaced with a
    visible marker so the user can see exactly where to type.
    """
    text = decode_mailto_escapes(text)
    filled: list[str] = []
    missing: list[str] = []
    out: list[str] = []
    cursor = 0
    for match in _PLACEHOLDER_RE.finditer(text):
        out.append(text[cursor : match.start()])
        kind, fillable = _read_blank(match, text, floor=cursor)
        cursor = match.end()
        value = fields.value_for(kind) if fillable else None
        if value:
            out.append(value)
            filled.append(kind)
        else:
            out.append(_MARKER_OPEN + LABELS[kind] + _MARKER_CLOSE)
            missing.append(kind)
    out.append(text[cursor:])
    return "".join(out), filled, missing


def _read_blank(match: "re.Match[str]", text: str, *, floor: int) -> tuple[str, bool]:
    """Work out what one matched blank stands for and whether it may be filled."""
    for group in _NEVER_FILLED_GROUPS:
        if match.group(group):
            return classify_token_text(match.group(group)), False
    for group in ("angle", "quoted_sample", "sample_email"):
        if match.group(group):
            kind = classify_token_text(match.group(group))
            return kind, kind in FILLABLE
    kind = classify_placeholder(text, match.start(), floor=floor)
    return kind, kind in FILLABLE


def has_email_template(entry: DeletionEntry) -> bool:
    """True when the entry carries wording to send, not only an address."""
    return bool(entry.email and entry.email_body)


def render_email_request(
    entry: DeletionEntry,
    *,
    profile: UserProfile,
    username: Optional[str] = None,
    from_email: Optional[str] = None,
) -> RenderedEmail:
    """Build the deletion email for a directory entry that ships wording.

    Raises ValueError when the entry has no body to work from. Callers that want
    a fallback should check ``has_email_template`` first.
    """
    if not entry.email_body:
        raise ValueError(
            f"'{entry.name}' has no email template in the directory. "
            "Use a jurisdiction letter instead."
        )
    fields = fields_from_profile(profile, username=username, from_email=from_email)
    body, body_filled, body_missing = fill_template_text(entry.email_body, fields)
    subject_raw = entry.email_subject or DEFAULT_SUBJECT
    subject, subj_filled, subj_missing = fill_template_text(subject_raw, fields)
    blanks = tuple(
        Blank(kind=kind, where=where, index=i)
        for where, kinds in (("body", body_missing), ("subject", subj_missing))
        for i, kind in enumerate(kinds, start=1)
    )
    return RenderedEmail(
        service=entry.name,
        to=entry.email or "",
        subject=subject,
        body=body,
        from_email=fields.email,
        blanks=blanks,
        filled=tuple(body_filled + subj_filled),
    )


def missing_field_lines(rendered: RenderedEmail) -> list[str]:
    """One line per spot the user still has to type in, with where it sits."""
    return [blank.describe() for blank in rendered.blanks]
