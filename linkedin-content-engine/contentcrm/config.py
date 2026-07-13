"""Config: scoring weights, cooldowns, slots, thresholds. Never constants in code."""
import copy
import json
from pathlib import Path

from . import ROOT

CONFIG_PATH = ROOT / "config.json"

DEFAULTS = {
    "db_path": "content.db",
    "default_platform": "linkedin",
    # PLAN.md starter formula, verbatim. Metrics without a weight here (e.g.
    # saves) are recorded but contribute 0 until a weight is added.
    "score_weights": {
        "bookings": 100,
        "link_clicks": 10,
        "profile_visits": 5,
        "reposts": 4,
        "comments": 3,
        "reactions": 1,
        "impressions": 0.01,
    },
    "cooldown_days": {"linkedin": 90, "x": 30, "instagram": 120},
    # Two comparable runs must differ by at least this much on the decision
    # metric before the tool calls a winner. Below it: noise, do not act.
    "min_effect_pct": 40,
    "decision_metric": "efficiency",  # efficiency | reach
    "checkpoints": {"24h": 24, "72h": 72, "7d": 168},
    # Hour ranges [start, end), local time; a range may wrap midnight.
    "slots": {
        "early-am": [5, 8],
        "mid-am": [8, 11],
        "midday": [11, 14],
        "afternoon": [14, 18],
        "evening": [18, 23],
        "night": [23, 5],
    },
    "status_window_days": 14,
}


def load_config(path=None):
    p = Path(path) if path else CONFIG_PATH
    cfg = copy.deepcopy(DEFAULTS)
    if p.exists():
        user = json.loads(p.read_text())
        cfg.update(user)
    return cfg


def db_path(cfg):
    p = Path(cfg["db_path"])
    return p if p.is_absolute() else ROOT / p


def write_default_config(path=None):
    p = Path(path) if path else CONFIG_PATH
    if p.exists():
        return False
    p.write_text(json.dumps(DEFAULTS, indent=2) + "\n")
    return True
