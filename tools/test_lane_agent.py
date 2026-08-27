"""Check the Lane Classifier's rules hold, without a network or a model.

    python -m tools.test_lane_agent

The classifier closes D29 and D32: a page that serves one route being filed
under another because that is where the walk found it. What it decides needs
real pages. What it is not allowed to do is checked here on a scripted model:

  1. A route is marked only with a sentence that is on the page. A quote that is
     not there is refused and told back to the agent.
  2. A page about neither route is a verdict, not a blank. `answered` is true and
     `about_a_route` is false.
  3. The verdict disagrees with the walk when the walk was wrong. That is the
     whole reason the agent exists.
  4. Model calls go through migragent.model. ADK's own client is trapped.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from migragent import model as model_module  # noqa: E402

WORK_PAGE = (
    "Skilled Worker visa. You can apply for a Skilled Worker visa to work for an "
    "approved employer in the United Kingdom. You must have a confirmation of "
    "sponsorship from that employer. The fee is 719 pounds."
)

STUDY_LINK_QUOTE = "If you want to study in the UK, you may be eligible for a Student visa."

TOURISM_PAGE = (
    "Visit the UK. You can visit the UK for up to 6 months as a tourist. You cannot "
    "work or study on a visit visa. You do not need to apply in advance if you hold "
    "certain passports."
)


def _fn(name: str, args: dict) -> dict:
    return {"candidates": [{"content": {"role": "model",
                                        "parts": [{"functionCall": {"name": name,
                                                                    "args": args}}]},
                            "finishReason": "STOP"}]}


class ScriptedModel:
    """Returns a fixed list of tool calls, and records the request bodies."""

    def __init__(self, script: list[dict]) -> None:
        self.script = script
        self.bodies: list[dict] = []
        self.step = 0

    def __call__(self, *, project, model, location, credentials, body):
        self.bodies.append(body)
        out = self.script[min(self.step, len(self.script) - 1)]
        self.step += 1
        return out


def run(script: list[dict], url: str, page: str):
    from migragent.agents.lane import LaneClassifier

    scripted = ScriptedModel(script)
    model_module.call_content = scripted

    import google.genai as genai

    class Trapped:
        def __init__(self, *a, **k):
            raise AssertionError("ADK built its own model client, bypassing migragent.model")

    real = genai.Client
    genai.Client = Trapped
    try:
        clf = LaneClassifier(project="p", model="gemini-3.5-flash",
                             location="global", credentials=None)
        verdict = clf.classify(url, page)
    finally:
        genai.Client = real
    return verdict, scripted


def main() -> int:
    results: list[tuple[bool, str, str]] = []

    def check(ok: bool, name: str, detail: str) -> None:
        results.append((bool(ok), name, detail))

    # Scenario one: a work page the walk filed under study.
    # The model first tries to mark study with a sentence that is NOT on the page
    # (the kind of link text a study index would carry), then marks work with a
    # real sentence, then finishes.
    verdict, scripted = run(
        [
            _fn("mark_lane", {"lane": "study", "quote": STUDY_LINK_QUOTE}),
            _fn("mark_lane", {"lane": "work",
                              "quote": "You must have a confirmation of sponsorship "
                                       "from that employer."}),
            _fn("finish", {}),
        ],
        "https://www.gov.uk/skilled-worker-visa", WORK_PAGE,
    )

    check(verdict.answered, "the classifier reached a verdict", verdict.error or "no error")
    check(verdict.serves("work") and not verdict.serves("study"),
          "only the route the page actually states was marked",
          f"lanes: {sorted(verdict.lanes)}")
    check(any(r["why"] == "the quote is not on the page" for r in verdict.refused),
          "a route marked with a sentence not on the page was refused",
          "; ".join(r["why"] for r in verdict.refused) or "nothing refused")
    check(not verdict.agrees_with("study"),
          "the verdict disagrees with the walk when the walk was wrong",
          f"walk said study; classifier says {sorted(verdict.lanes)}")
    check(verdict.evidence.get("work", "") in WORK_PAGE,
          "the kept route carries a sentence from the page",
          verdict.evidence.get("work", "none"))

    # Model routing and tool placement.
    check(len(scripted.bodies) > 0 and all("tools" in b for b in scripted.bodies[:1]),
          "model calls went through migragent.model with tools at the top level",
          f"{len(scripted.bodies)} call(s); first body keys: "
          f"{sorted(scripted.bodies[0]) if scripted.bodies else 'none'}")
    first = scripted.bodies[0] if scripted.bodies else {}
    declared = []
    for tool in first.get("tools", []):
        declared += [d["name"] for d in tool.get("functionDeclarations", [])]
    check(set(declared) >= {"mark_lane", "mark_none", "finish"},
          "the three tools are declared",
          f"declared: {', '.join(sorted(declared)) or 'none'}")
    check("tools" not in first.get("generationConfig", {}),
          "tools did not get mixed into the sampling settings",
          f"generationConfig: {sorted(first.get('generationConfig', {}))}")

    # Scenario two: a page about neither route.
    verdict2, _ = run(
        [
            _fn("mark_none", {"quote": "You cannot work or study on a visit visa."}),
            _fn("finish", {}),
        ],
        "https://www.gov.uk/visit-uk", TOURISM_PAGE,
    )
    check(verdict2.answered and not verdict2.about_a_route,
          "a page about neither route is a verdict, not a blank",
          f"lanes: {sorted(verdict2.lanes)}; off-topic quote: "
          f"{verdict2.off_topic_quote!r}")
    check(not verdict2.agrees_with("study") and not verdict2.agrees_with("work"),
          "an off-route page is filed under no lane",
          f"serves study: {verdict2.serves('study')}, work: {verdict2.serves('work')}")

    # Scenario three: an invented off-topic quote is refused too.
    verdict3, _ = run(
        [
            _fn("mark_none", {"quote": "This page is about applying for citizenship."}),
            _fn("finish", {}),
        ],
        "https://www.gov.uk/visit-uk", TOURISM_PAGE,
    )
    check(not verdict3.answered and any(r["lane"] == "none" for r in verdict3.refused),
          "an off-topic sentence not on the page is refused like any other",
          f"answered: {verdict3.answered}; refused: {verdict3.refused}")

    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        print(f"        {detail}")

    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
