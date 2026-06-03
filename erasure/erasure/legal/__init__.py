"""GDPR/CCPA compliance, evidence generation, and legal request templates."""

from erasure.legal.generator import (
    build_identifiers_block,
    render_request,
    save_request,
)
from erasure.legal.templates import JURISDICTIONS, Jurisdiction

__all__ = [
    "build_identifiers_block",
    "render_request",
    "save_request",
    "JURISDICTIONS",
    "Jurisdiction",
]
