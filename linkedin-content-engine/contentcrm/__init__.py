"""Content CRM: library, lineage and recycling for Alex's posts.

The model, non-negotiable: an idea is durable; a variant is one written
expression of an idea for one platform, and variants have parents; a run is
one publication of one variant at one moment. Metrics attach to runs.

The tool never posts. Alex publishes by hand; this records what happened.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
