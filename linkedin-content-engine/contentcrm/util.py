"""Time buckets, slugs, small shared helpers."""
import re
from datetime import datetime

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def parse_when(text=None):
    """Parse a user-supplied publish time into (iso_string, precision).

    Accepts 'YYYY-MM-DD HH:MM', 'YYYY-MM-DDTHH:MM', 'YYYY-MM-DD', a leading
    '~' for approximate dates, or None/'now' for the current minute.
    Precision drives the comparison gates: 'minute' knows dow+slot, 'date'
    knows dow only, 'approx' knows neither.
    """
    if not text or text.strip().lower() == "now":
        return now_iso(), "minute"
    t = text.strip()
    approx = t.startswith("~")
    if approx:
        t = t.lstrip("~").strip()
    for fmt, prec in (
        ("%Y-%m-%d %H:%M", "minute"),
        ("%Y-%m-%dT%H:%M", "minute"),
        ("%Y-%m-%d", "date"),
    ):
        try:
            dt = datetime.strptime(t, fmt)
        except ValueError:
            continue
        if approx:
            return dt.strftime("%Y-%m-%d"), "approx"
        if prec == "minute":
            return dt.strftime("%Y-%m-%d %H:%M"), "minute"
        return dt.strftime("%Y-%m-%d"), "date"
    raise ValueError(
        f"cannot parse {text!r}: use 'YYYY-MM-DD HH:MM', 'YYYY-MM-DD', or '~YYYY-MM-DD' for approximate"
    )


def dow_bucket(posted_at, precision):
    if precision == "approx":
        return None
    return DOW[datetime.strptime(posted_at[:10], "%Y-%m-%d").weekday()]


def slot_bucket(posted_at, precision, slots):
    if precision != "minute":
        return None
    hour = datetime.strptime(posted_at, "%Y-%m-%d %H:%M").hour
    for name, bounds in slots.items():
        start, end = bounds
        if start <= end:
            if start <= hour < end:
                return name
        elif hour >= start or hour < end:  # range wraps midnight
            return name
    return None


def elapsed_hours(posted_at, ref=None):
    """Hours since posting. Date-only timestamps count from midnight."""
    fmt = "%Y-%m-%d %H:%M" if len(posted_at) > 10 else "%Y-%m-%d"
    start = datetime.strptime(posted_at, fmt)
    ref = ref or datetime.now()
    return (ref - start).total_seconds() / 3600.0


def slugify(text, max_len=36):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    if len(s) > max_len:
        cut = s[:max_len].rstrip("-")
        # trim at a word boundary unless that throws away most of the slug
        if "-" in cut[max_len // 2:]:
            cut = cut.rsplit("-", 1)[0]
        s = cut
    return s or "untitled"


def unique_slug(conn, base):
    slug, n = base, 2
    while conn.execute("SELECT 1 FROM ideas WHERE slug = ?", (slug,)).fetchone():
        slug = f"{base}-{n}"
        n += 1
    return slug


def fmt_num(value, decimals=3):
    if value is None:
        return "n/a"
    return f"{value:.{decimals}f}"
