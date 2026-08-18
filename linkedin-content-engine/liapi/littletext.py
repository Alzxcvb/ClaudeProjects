"""Escape plain text for the Posts API `commentary` field.

The Posts API does not take plain text. It takes LinkedIn's "little" format,
and their documentation is blunt about what that costs you:

    "All reserved characters need to be escaped with a backslash, even if those
    characters are not used in one of the supported elements or templates."

The reserved set, from the Text grammar rule:

    |  {  }  @  [  ]  (  )  <  >  #  \\  *  _  ~

This matters more than it looks. Alex's posts are full of parentheses and
underscores. Sending them raw means LinkedIn tries to read them as mention or
hashtag syntax, and the copy either comes out mangled or the request is
rejected, live, on a feed carrying his real name and his PE credential.

The one deliberate exception is hashtags. A bare `#word` is a valid
HashtagElement, and escaping it to `\\#word` would render the text "#word"
instead of a real clickable hashtag. Since Alex adds hashtags to his posts by
hand, escaping them would quietly strip a feature he is using. So a `#`
followed by word characters is passed through whole, and every other `#` is
escaped.

The ugcPosts API does NOT use this format. Its shareCommentary.text is plain
text, which is exactly why escaping is applied per endpoint and never globally.
"""
import re

# Every character the little grammar reserves. Order is irrelevant here because
# the implementation walks the string once instead of running chained replaces,
# which is what prevents double-escaping WITHIN a pass. escape() is not
# idempotent: applied to already-escaped text it would double the backslashes,
# so it is called exactly once, at the publish boundary.
RESERVED = set("|{}@[]()<>#\\*_~")

# A hashtag worth preserving: # or the fullwidth ＃, then at least one word char.
_HASHTAG = re.compile(r"[#＃][A-Za-z0-9_]+")


def escape(text, preserve_hashtags=True):
    """Turn plain text into little format.

    With preserve_hashtags, a real hashtag survives as a hashtag. Without it,
    every reserved character becomes literal, which is the safest possible
    output and useful when copy happens to contain a stray '#'.
    """
    if text is None:
        return None

    spans = []
    if preserve_hashtags:
        spans = [(m.start(), m.end()) for m in _HASHTAG.finditer(text)]

    out = []
    i = 0
    length = len(text)
    span_idx = 0
    while i < length:
        # Pass an entire hashtag token through untouched.
        if span_idx < len(spans) and i == spans[span_idx][0]:
            start, end = spans[span_idx]
            out.append(text[start:end])
            i = end
            span_idx += 1
            continue
        ch = text[i]
        if ch in RESERVED:
            out.append("\\" + ch)
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def needs_escaping(text):
    """True when the text contains anything the little grammar reserves."""
    return any(ch in RESERVED for ch in (text or ""))


def find_reserved(text):
    """Which reserved characters appear anywhere in the text."""
    return sorted({ch for ch in (text or "") if ch in RESERVED})


def escaped_chars(text, preserve_hashtags=True):
    """Which characters escaping ACTUALLY changed.

    This is not the same as find_reserved. A preserved hashtag leaves its `#`
    untouched, so reporting every reserved character as "escaped" would tell a
    human something false on the one screen where they approve what goes out.
    """
    out = escape(text, preserve_hashtags=preserve_hashtags)
    changed = set()
    i = 0
    while i < len(out):
        if out[i] == "\\" and i + 1 < len(out):
            changed.add(out[i + 1])
            i += 2
        else:
            i += 1
    return sorted(changed)
