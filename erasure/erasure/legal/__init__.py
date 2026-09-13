"""GDPR/CCPA compliance, evidence generation, and legal request templates."""

from erasure.legal.email_templates import (
    RenderedEmail,
    TemplateFields,
    fill_template_text,
    has_email_template,
    missing_field_lines,
    render_email_request,
)
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
    "RenderedEmail",
    "TemplateFields",
    "fill_template_text",
    "has_email_template",
    "missing_field_lines",
    "render_email_request",
]
