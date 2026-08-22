"""The run: the work the agent does for one case, emitted step by step.

Every step here is real work. Each one is yielded the moment it finishes, with
the number it actually produced and the seconds it actually took.

There is no sleep in this file and no artificial pacing. If matching a hundred
requirements takes six seconds then the line sits on screen for six seconds, and
if a step produces nothing then it says nothing rather than being skipped so the
list looks busier.

That restraint is not decoration. The screen it feeds is the first thing a person
sees before deciding whether to trust a guide with their savings, and a progress
bar that is really a timer is the same lie as an invented citation told in a
different medium.

What this file does contribute to the estimated wait on that screen is the one
honest ingredient: how long the run really took, recorded when it finishes and
only when it finishes. Runs that died are not evidence of how long a run takes.
"""
from __future__ import annotations

import json
import time
from typing import Any, Iterator


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _took(seconds: float) -> str:
    return f"{seconds:.1f}s"


class Run:
    """Does the work for one case and reports honestly as it goes."""

    def __init__(self, *, cases, corpus, registry, matcher, finder, builder,
                 detect_fn, agreement_fn, times=None, cvs=None) -> None:
        self._cases = cases
        self._corpus = corpus
        self._registry = registry
        self._matcher = matcher
        self._finder = finder
        self._builder = builder
        self._detect = detect_fn
        self._agreement = agreement_fn
        # Optional, because a Run is constructed in tests and tools that have no
        # interest in bookkeeping. Where it is present, every finished run tells
        # the next person how long to expect to wait.
        self._times = times
        # Optional, so tools that build a Run without one keep working.
        self._cvs = cvs

    def stream(self, case) -> Iterator[str]:
        started = time.monotonic()
        finished = False

        try:
            yield from self._steps(case)
            finished = True
        except Exception as exc:  # noqa: BLE001
            yield _sse({"event": "error", "what": "The run stopped",
                        "detail": f"{type(exc).__name__}: {exc}"})

        took = time.monotonic() - started

        # Only a run that got all the way through is evidence of how long a run
        # takes. One that died after four seconds would drag every future
        # estimate down and make the screen promise a wait it cannot keep.
        if finished and self._times is not None:
            self._times.record(case.jurisdiction, case.lane,
                               getattr(case, "document_count", 0) or 0, took)

        yield _sse({"event": "done", "took": _took(took)})

    def _steps(self, case) -> Iterator[str]:
        lane_name = f"{case.jurisdiction} {case.lane}"

        # 1. What we hold for this lane.
        t = time.monotonic()
        near = {s.url.rstrip("/") for s in self._registry.near_lane(case.jurisdiction, case.lane)}
        requirements = self._corpus.requirements_for(case.jurisdiction, case.lane,
                                                     allowed_urls=near)
        questions = self._corpus.open_questions_for(case.jurisdiction, case.lane,
                                                    allowed_urls=near)
        yield _sse({
            "what": f"Opened the {lane_name} sources",
            "detail": (f"{len(requirements)} requirements read from {len(near)} official pages, "
                       f"{len(questions)} open questions already recorded"),
            "took": _took(time.monotonic() - t),
        })

        # 2. The documents, each one its own step, with the words checked against
        #    what the model called it.
        documents = self._cases.documents(case.case_id)
        for doc in documents:
            t = time.monotonic()
            state, sentence = doc.agreement_state, doc.agreement_note
            verified = len(doc.verified_fields)
            detail = (f"{len(doc.fields)} fields, {verified} verified against the document's own "
                      f"text. {sentence}")
            yield _sse({
                "what": f"Read {doc.filename} as a {doc.kind.replace('_', ' ')}"
                        + ("" if state != "disagreed" else "  (the words disagree)"),
                "detail": detail,
                "took": _took(time.monotonic() - t),
            })

        # A CV lives in its own store rather than with the documents, because it
        # answers nobody's question: it is a claim a person makes about
        # themselves, not an answer to something a government asked. See cv.py.
        #
        # It still has to be visible here. Uploading a CV on the work path and
        # then being told "no documents to read" is the product losing your file
        # as far as you can tell, and that is exactly what it looked like.
        cv = self._cvs.get(case.case_id) if self._cvs else None
        if cv is not None:
            verified = len(cv.verified)
            yield _sse({
                "what": f"Read your CV: {cv.filename}",
                "detail": (f"{len(cv.claims)} things it says about you, {verified} of them "
                           f"checked word for word against the file. This is what the job "
                           f"matching runs on. It does not answer the document requirements "
                           f"below, because a CV is not a passport."),
                "took": "",
            })

        if not documents and cv is None:
            yield _sse({
                "what": "No documents to read",
                "detail": "The guide will be the general one for this lane rather than yours.",
                "took": "",
            })

        # 3. Matching.
        t = time.monotonic()
        coverage = self._matcher.match(case.jurisdiction, case.lane, requirements, documents)
        self._cases.save_coverage(case.case_id, coverage.to_dict())
        dropped = len(coverage.dropped_matches)
        detail = (f"{coverage.covered} of {coverage.document_requirements} requirements a "
                  f"document could answer, so the score is {coverage.score}%. "
                  f"{coverage.action_only} are actions or fees that no document covers.")
        if dropped:
            detail += f" {dropped} proposed matches dropped for citing something you did not upload."
        yield _sse({
            "what": "Matched what you have against what this lane asks for",
            "detail": detail,
            "took": _took(time.monotonic() - t),
        })

        # 4. Routes, for the biggest gaps only. Each is a model call, so this is
        #    capped rather than run across every unmatched requirement.
        gaps = coverage.unmatched[:4]
        routes: list[dict[str, Any]] = []
        for gap in gaps:
            t = time.monotonic()
            route, _dropped = self._finder.find(gap, requirements)
            routes.append(route.to_dict())
            if route.has_options:
                detail = "; ".join(o.name for o in route.options[:3])
            else:
                detail = route.no_route_reason or "no route found"
            yield _sse({
                "what": f"Looked for a way through: {gap.get('text','')[:70]}",
                "detail": detail,
                "took": _took(time.monotonic() - t),
            })

        # 5. The form.
        t = time.monotonic()
        form = self._builder.build(case.case_id, case.created_at, coverage.unmatched)
        detail = f"{len(form.questions)} questions, covering what your documents do not answer."
        if form.dropped:
            detail += f" {len(form.dropped)} rejected for being too broad to mean anything."
        yield _sse({
            "what": "Wrote the questions only you can answer",
            "detail": detail,
            "took": _took(time.monotonic() - t),
        })

        # 6. Save what the result page will read.
        t = time.monotonic()
        self._cases.save_result(case.case_id, {
            "routes": routes,
            "form": form.to_dict(),
            "requirement_count": len(requirements),
            "source_count": len(near),
        })
        yield _sse({
            "what": "Assembled your guide",
            "detail": f"{len(requirements)} requirements, each with the page it came from and "
                      f"the date that page was read.",
            "took": _took(time.monotonic() - t),
        })

def sse_done() -> str:
    """A stream that ends immediately, for a request with no case."""
    return _sse({"event": "done"})
