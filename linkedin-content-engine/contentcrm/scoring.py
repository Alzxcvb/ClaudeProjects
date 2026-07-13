"""Score, efficiency, normalised reach.

Never compare raw impressions across time: follower count moves underneath
you. Comparison happens on efficiency (score / impressions) and normalised
reach (impressions / followers_at_post). Weights come from config only.
"""
from .db import latest_metrics


def score(metrics_row, weights):
    """Weighted score over one snapshot. Metrics absent from the weights dict
    contribute nothing; NULL values count as 0."""
    keys = metrics_row.keys()
    total = 0.0
    for field, w in weights.items():
        v = metrics_row[field] if field in keys else None
        total += w * (v or 0)
    return total


def efficiency(score_value, impressions):
    if not impressions:
        return None
    return score_value / impressions


def normalised_reach(impressions, followers_at_post):
    if not impressions or not followers_at_post:
        return None
    return impressions / followers_at_post


def run_performance(conn, run, cfg, snapshot=None):
    """Performance for one run row from a given snapshot (default: latest),
    or None if the run has no metrics."""
    m = snapshot if snapshot is not None else latest_metrics(conn, run["id"])
    if m is None:
        return None
    s = score(m, cfg["score_weights"])
    return {
        "metrics": m,
        "checkpoint": m["checkpoint"],
        "captured_at": m["captured_at"],
        "impressions": m["impressions"],
        "score": s,
        "efficiency": efficiency(s, m["impressions"]),
        "reach": normalised_reach(m["impressions"], run["followers_at_post"]),
    }
