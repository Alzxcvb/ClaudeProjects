"""Deletion-request letter templates, by jurisdiction.

Each template cites the specific statute that gives the requester the right to
deletion and sets a response clock. The bodies are format strings filled by
``erasure.legal.generator``. Copy is deliberately plain (no em dashes) so the
output reads as a human-written letter, not boilerplate.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Jurisdiction:
    key: str
    label: str
    statutes: tuple[str, ...]
    default_deadline_days: int
    body: str


_CCPA_BODY = """\
{date}

To: {recipient_name}
Re: Request to Delete and Stop the Sale of My Personal Information

To Whom It May Concern,

I am a California resident exercising my rights under the California Consumer \
Privacy Act (CCPA), as amended by the California Privacy Rights Act (CPRA). \
Under California Civil Code section 1798.105, I request that you delete all \
personal information you have collected about me. Under California Civil Code \
section 1798.120, I direct you to stop selling and sharing my personal \
information with third parties.

You can identify me using the following information:

{identifiers_block}

Under California Civil Code section 1798.130, please confirm completion of \
this request in writing within {deadline_days} days. If you are a registered \
data broker, this request is also made under the California Delete Act \
(SB 362), and I ask that you forward this deletion request to any third \
parties and service providers with whom you have shared my information.

If you deny any part of this request, please state the specific statutory \
exemption you are relying on.

Sincerely,
{requester_name}
"""


_GDPR_BODY = """\
{date}

To: {recipient_name}
Re: Request for Erasure and Objection to Processing

To Whom It May Concern,

I am exercising my rights under the EU General Data Protection Regulation \
(GDPR). Under Article 17, I request the erasure of all personal data you hold \
concerning me. Under Article 21, I object to the processing of my personal \
data, including any processing for direct marketing or for the sale of my data \
to third parties.

You can identify me using the following information:

{identifiers_block}

Under Article 12(3), please confirm completion of this request without undue \
delay and in any event within {deadline_days} days. Where you have made my \
personal data public or shared it with other controllers, Article 17(2) \
requires you to inform those controllers of this erasure request.

If you refuse to act on this request, Article 12(4) requires you to inform me \
of the reasons and of my right to lodge a complaint with a supervisory \
authority.

Sincerely,
{requester_name}
"""


_GENERIC_BODY = """\
{date}

To: {recipient_name}
Re: Request to Delete My Personal Information

To Whom It May Concern,

I request that you delete all personal information you hold about me and that \
you stop selling or sharing it with third parties. Depending on my \
jurisdiction, this request is made under applicable data protection law, which \
may include the California Consumer Privacy Act, the California Delete Act, or \
the EU General Data Protection Regulation.

You can identify me using the following information:

{identifiers_block}

Please confirm completion of this request in writing within {deadline_days} \
days. If you share my information with third parties, please forward this \
request to them as well.

If you deny this request, please state the specific legal basis for the denial.

Sincerely,
{requester_name}
"""


CCPA = Jurisdiction(
    key="ccpa",
    label="California Consumer Privacy Act (CCPA/CPRA) + Delete Act",
    statutes=(
        "Cal. Civ. Code 1798.105",
        "Cal. Civ. Code 1798.120",
        "Cal. Civ. Code 1798.130",
        "SB 362 (California Delete Act)",
    ),
    default_deadline_days=45,
    body=_CCPA_BODY,
)

GDPR = Jurisdiction(
    key="gdpr",
    label="EU General Data Protection Regulation (GDPR)",
    statutes=("GDPR Article 17", "GDPR Article 21", "GDPR Article 12"),
    default_deadline_days=30,
    body=_GDPR_BODY,
)

GENERIC = Jurisdiction(
    key="generic",
    label="Generic (cites CCPA, Delete Act, and GDPR)",
    statutes=("CCPA", "California Delete Act", "GDPR"),
    default_deadline_days=45,
    body=_GENERIC_BODY,
)

JURISDICTIONS: dict[str, Jurisdiction] = {j.key: j for j in (CCPA, GDPR, GENERIC)}
