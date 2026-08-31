"""Matching what somebody has against what a lane requires.

This produces the readiness score, and the score is the thing in this build most
likely to become a lie.

A number that climbs because a file arrived is a progress bar wearing an
assessment's clothes. It would feel good, it would fire confetti, and it would
tell somebody they are 70% ready for a study permit on the strength of having
uploaded a gym membership. So the score is not a count of uploads. It is the
share of the lane's extracted requirements that the uploaded documents can be
shown to address.

HOW A MATCH IS EVIDENCED
------------------------
A model proposes matches. Each one has to name the document field it relies on,
and that field has to exist on a document actually uploaded. A match citing a
field nobody uploaded is dropped and counted, the same discipline as everywhere
else.

WHAT THE SCORE IS NOT
---------------------
It is not a prediction that an application will succeed, and nothing here says
or implies that. It is the proportion of requirements we have read for this lane
that your documents currently speak to. Requirements that no document can
satisfy, because they are actions rather than papers, are counted separately and
never held against you.

DOCUMENT WORTH IS COMPUTED, NOT DECLARED
----------------------------------------
The upload list is ordered by how many requirements each kind of document can
actually address in this lane, counted from the corpus. Nobody decides in
advance that a passport is worth more than a school transcript. It is worth more
because more requirements turn out to depend on it, and in a lane where that is
not true the order changes by itself.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from .documents import ReadDocument
from .model import call_json

# Requirements that no document can ever satisfy, because they describe
# something you do rather than something you hold. Counted apart so they do not
# drag a score down for a reason the person cannot act on by uploading.
ACTION_CATEGORIES = {"timing", "cost"}

# How many requirements go into the one matching call.
#
# The score's denominator is every requirement a document could answer, so a
# requirement left out of the call can never be matched and quietly costs
# somebody a point they had earned. This was 200, and UK study now holds 201
# satisfiable requirements, so the cap had started to bite: measured on 31
# August 2026, 290 requirements read for that lane, 89 of them actions or fees.
#
# It is still a cap rather than no cap, because a prompt has to end somewhere.
# Raising it costs prompt size and not a second call, which is the trade worth
# making while one call still fits.
MAX_REQUIREMENTS_PER_CALL = 400


@dataclass
class Match:
    """One requirement, addressed by one document."""

    requirement_id: str
    requirement_text: str
    document_kind: str
    document_field: str
    field_value: str
    verified: bool
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Coverage:
    """What the uploads cover, and what they do not."""

    jurisdiction: str
    lane: str
    total_requirements: int = 0
    document_requirements: int = 0
    matched: list[Match] = field(default_factory=list)
    unmatched: list[dict[str, str]] = field(default_factory=list)
    action_only: int = 0
    dropped_matches: list[dict[str, str]] = field(default_factory=list)

    @property
    def covered(self) -> int:
        return len({m.requirement_id for m in self.matched})

    @property
    def score(self) -> int:
        """Whole per cent of the document-satisfiable requirements addressed.

        Rounded down, never up. A score that rounds 69.6 to 70 is flattering
        itself, and this number is going to be shown next to confetti.
        """
        if not self.document_requirements:
            return 0
        return int(self.covered * 100 // self.document_requirements)

    @property
    def unverified_count(self) -> int:
        return sum(1 for m in self.matched if not m.verified)

    def to_dict(self) -> dict[str, Any]:
        return {
            "jurisdiction": self.jurisdiction,
            "lane": self.lane,
            "score": self.score,
            "covered": self.covered,
            "document_requirements": self.document_requirements,
            "total_requirements": self.total_requirements,
            "action_only": self.action_only,
            "unverified": self.unverified_count,
            "matched": [m.to_dict() for m in self.matched],
            "unmatched": self.unmatched[:200],
            "dropped_matches": self.dropped_matches[:50],
        }


PROMPT = """You are checking which requirements a person's documents already \
address.

DOCUMENTS THEY UPLOADED:
{documents}

REQUIREMENTS FOR THIS APPLICATION:
{requirements}

For each requirement that one of the documents addresses, return:
  {{"requirement_id": "...", "document_kind": "...", "document_field": "...", \
"note": "one short sentence on why this document addresses it"}}

Rules:
- "document_kind" must be one of the kinds listed above. "document_field" must \
be one of the field names listed under that document. Both are checked and any \
match naming something that was not uploaded is discarded.
- Only claim a match where the document genuinely addresses the requirement. \
Leaving a requirement unmatched is a correct answer and is more useful than a \
generous one.
- Do not match a requirement that describes an action, a fee or a waiting time \
to a document.

Return only JSON: {{"matches": [...]}}"""


class Matcher:
    """Works out what the uploads cover."""

    def __init__(self, project: str, model: str, location: str, credentials: Any) -> None:
        self._project = project
        self._model = model
        self._location = location
        self._credentials = credentials

    def _call(self, prompt: str):
        """Delegates to migragent.model, which retries and reports properly.

        Every caller used to carry its own copy of this and none of them
        retried, so one run hitting the quota produced three unrelated
        looking symptoms. See D20.
        """
        return call_json(
            project=self._project, model=self._model,
            location=self._location, credentials=self._credentials,
            parts=[{"text": prompt}],
        )

    def match(self, jurisdiction: str, lane: str,
              requirements: list[dict[str, Any]],
              documents: list[ReadDocument]) -> Coverage:
        coverage = Coverage(jurisdiction=jurisdiction, lane=lane,
                            total_requirements=len(requirements))

        satisfiable = [r for r in requirements
                       if r.get("category") not in ACTION_CATEGORIES]
        coverage.document_requirements = len(satisfiable)
        coverage.action_only = len(requirements) - len(satisfiable)

        if not documents or not satisfiable:
            coverage.unmatched = [
                {"requirement_id": r.get("id", ""), "text": r.get("text", "")}
                for r in satisfiable
            ]
            return coverage

        doc_lines = []
        available: dict[str, dict[str, tuple[str, bool]]] = {}
        for doc in documents:
            fields = {f.name: (f.value, f.verified) for f in doc.fields}
            available[doc.kind] = {**available.get(doc.kind, {}), **fields}
            listing = ", ".join(sorted(fields)) or "no readable fields"
            doc_lines.append(f"- {doc.kind} ({doc.filename}): {listing}")

        req_lines = [f'- id={r.get("id","")}: {r.get("text","")}' for r in satisfiable]

        try:
            parsed = self._call(PROMPT.format(
                documents="\n".join(doc_lines),
                requirements="\n".join(req_lines[:MAX_REQUIREMENTS_PER_CALL]),
            ))
        except Exception as exc:  # noqa: BLE001
            coverage.dropped_matches.append({"why": str(exc)})
            coverage.unmatched = [
                {"requirement_id": r.get("id", ""), "text": r.get("text", "")}
                for r in satisfiable
            ]
            return coverage

        by_id = {r.get("id", ""): r for r in satisfiable}
        for item in parsed.get("matches", []):
            rid = str(item.get("requirement_id") or "")
            kind = str(item.get("document_kind") or "")
            fname = str(item.get("document_field") or "")

            if rid not in by_id:
                coverage.dropped_matches.append(
                    {"requirement_id": rid, "why": "no such requirement in this lane"})
                continue
            if kind not in available or fname not in available[kind]:
                # The match leans on something nobody uploaded. Exactly the kind
                # of confident, plausible, invented result the whole build
                # guards against.
                coverage.dropped_matches.append({
                    "requirement_id": rid,
                    "why": f"cites {kind}.{fname}, which was not uploaded",
                })
                continue

            value, verified = available[kind][fname]
            coverage.matched.append(Match(
                requirement_id=rid,
                requirement_text=by_id[rid].get("text", ""),
                document_kind=kind,
                document_field=fname,
                field_value=value,
                verified=verified,
                note=str(item.get("note") or ""),
            ))

        covered_ids = {m.requirement_id for m in coverage.matched}
        coverage.unmatched = [
            {"requirement_id": r.get("id", ""), "text": r.get("text", "")}
            for r in satisfiable if r.get("id", "") not in covered_ids
        ]
        return coverage


def document_worth(requirements: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """Order document kinds by how many of this lane's requirements mention them.

    Counted from the corpus rather than declared. The ordering shown to somebody
    deciding what to dig out of a drawer should reflect what actually unlocks
    requirements in the lane they picked, not a list somebody once ranked by
    intuition.

    This is a word count over requirement text, which is a heuristic over names
    and would be unacceptable for deciding what a requirement IS. It is
    acceptable here because it decides only the ORDER of a list of prompts, and
    getting it wrong costs somebody a moment's scrolling rather than a false
    claim in a guide.
    """
    terms = {
        "passport": ("passport", "travel document"),
        "english_test": ("english", "ielts", "toefl", "language test"),
        "offer_letter": ("acceptance", "offer", "letter of acceptance", "admission"),
        "bank_statement": ("proof of funds", "bank statement", "enough money",
                           "financial support", "guaranteed investment certificate"),
        "transcript": ("transcript", "academic record", "results"),
        # "certificate" on its own was catching police certificates, medical
        # certificates and birth certificates, and put degree_certificate top of
        # the list with 80 against Canada study. Measured, then narrowed.
        "degree_certificate": ("degree certificate", "degree", "diploma",
                               "qualification", "graduation"),
        "police_certificate": ("police certificate", "police clearance", "criminal record",
                               "criminal check", "character requirement"),
        "medical_exam": ("medical exam", "medical examination", "panel physician",
                         "immunis", "immuniz", "chest x-ray"),
        "birth_certificate": ("birth certificate", "date of birth"),
        "employment_letter": ("employment", "employer", "job offer", "work experience"),
        "professional_registration": ("registration", "licence", "license", "regulator"),
        "marriage_certificate": ("marriage", "spouse", "partner"),
        "national_id": ("national identity", "identity card"),
    }
    counts: Counter[str] = Counter()
    for req in requirements:
        text = (req.get("text", "") + " " + req.get("quote", "")).lower()
        for kind, needles in terms.items():
            if any(n in text for n in needles):
                counts[kind] += 1
    ordered = counts.most_common()
    for kind in terms:
        if kind not in counts:
            ordered.append((kind, 0))
    return ordered
