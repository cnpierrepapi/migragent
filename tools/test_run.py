"""What the run reports, and what it files away about how long it took.

Offline. Every collaborator is a stand in, so this asserts the run's own
bookkeeping rather than anything a model said.

The one this exists for: the timing bucket. A finished run is filed under how
many files it read, and the working screen reads its estimate back out of the
same bucket. Those two counts have to be the same number or the estimate never
finds a sample and the no-documents bucket fills with other people's runs. They
were not the same number: the run filed `case.document_count`, which nothing has
ever written.
"""
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from migragent.coverage import Coverage  # noqa: E402
from migragent.run import Run  # noqa: E402

passed = failed = 0


def check(ok, name, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}  {detail}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


@dataclass
class FakeCase:
    case_id: str = "case-1"
    jurisdiction: str = "CA"
    lane: str = "study"
    created_at: str = "2026-08-31T00:00:00+00:00"


@dataclass
class FakeField:
    name: str = "expiry"
    value: str = "2034-01-08"
    verified: bool = True


@dataclass
class FakeDoc:
    filename: str
    kind: str = "passport"
    fields: list = field(default_factory=lambda: [FakeField()])
    text_layer: bool = True
    agreement_state: str = "agreed"
    agreement_note: str = "the words agree"

    @property
    def verified_fields(self):
        return [f for f in self.fields if f.verified]


@dataclass
class FakeClaim:
    verified: bool = True


@dataclass
class FakeCV:
    filename: str = "cv.pdf"
    text_layer: bool = True
    claims: list = field(default_factory=lambda: [FakeClaim()])

    @property
    def verified(self):
        return [c for c in self.claims if c.verified]


class FakeCases:
    def __init__(self, documents):
        self._documents = documents
        self.coverage = None
        self.result = None

    def documents(self, case_id):
        return list(self._documents)

    def save_coverage(self, case_id, payload):
        self.coverage = payload

    def save_result(self, case_id, payload):
        self.result = payload


class FakeCorpus:
    def requirements_for(self, j, lane, allowed_urls=None):
        return [{"id": "r1", "text": "A valid passport", "category": "document"},
                {"id": "r2", "text": "Pay the fee", "category": "cost"}]

    def open_questions_for(self, j, lane, allowed_urls=None):
        return []


@dataclass
class FakeSource:
    url: str = "https://example.gov/a"


class FakeRegistry:
    def near_lane(self, j, lane):
        return [FakeSource()]


class FakeMatcher:
    def match(self, j, lane, requirements, documents):
        cov = Coverage(jurisdiction=j, lane=lane, total_requirements=len(requirements))
        cov.document_requirements = 1
        cov.action_only = 1
        cov.unmatched = [{"requirement_id": "r1", "text": "A valid passport"}]
        return cov


@dataclass
class FakeRoute:
    has_options: bool = False
    no_route_reason: str = "no route found"
    options: list = field(default_factory=list)

    def to_dict(self):
        return {"reason": self.no_route_reason}


class FakeFinder:
    def find(self, gap, requirements):
        return FakeRoute(), []


@dataclass
class FakeForm:
    questions: list = field(default_factory=list)
    dropped: list = field(default_factory=list)

    def to_dict(self):
        return {"questions": self.questions}


class FakeBuilder:
    def build(self, case_id, created_at, unmatched):
        return FakeForm()


class FakeCVs:
    def __init__(self, cv):
        self._cv = cv

    def get(self, case_id):
        return self._cv


class FakeTimes:
    def __init__(self):
        self.recorded = []

    def record(self, jurisdiction, lane, documents, seconds):
        self.recorded.append((jurisdiction, lane, documents, seconds))


def run_once(documents, cv):
    times = FakeTimes()
    cases = FakeCases(documents)
    run = Run(cases=cases, corpus=FakeCorpus(), registry=FakeRegistry(),
              matcher=FakeMatcher(), finder=FakeFinder(), builder=FakeBuilder(),
              detect_fn=lambda *a, **k: None, agreement_fn=lambda *a, **k: ("", ""),
              times=times, cvs=FakeCVs(cv))
    events = [json.loads(chunk.removeprefix("data: ").strip())
              for chunk in run.stream(FakeCase())]
    return events, times, cases


print("what the run records about how long it took")

events, times, cases = run_once([FakeDoc("passport.pdf"), FakeDoc("transcript.pdf"),
                                 FakeDoc("ielts.pdf")], None)
check(len(times.recorded) == 1, "a finished run is recorded once", str(times.recorded))
check(times.recorded[0][2] == 3, "three documents are filed as three",
      f"filed {times.recorded[0][2]}")

events, times, _ = run_once([FakeDoc("degree.pdf")], FakeCV())
check(times.recorded[0][2] == 2,
      "a CV counts too, the way the working screen counts it",
      f"filed {times.recorded[0][2]}")

events, times, _ = run_once([], None)
check(times.recorded[0][2] == 0, "nothing uploaded is filed as none",
      f"filed {times.recorded[0][2]}")
check(any(e.get("what") == "No documents to read" for e in events),
      "and the stream says so rather than skipping the step")

print()
print("what the stream reports")
events, times, cases = run_once([FakeDoc("passport.pdf")], None)
check(events[-1].get("event") == "done", "the last event closes the stream")
check(any("Opened the CA study sources" in (e.get("what") or "") for e in events),
      "it opens with what we hold for the lane")
check(any("Read passport.pdf" in (e.get("what") or "") for e in events),
      "every document gets its own step")
check(cases.coverage is not None and cases.result is not None,
      "the coverage and the result are both saved")
check(cases.result.get("source_count") == 1 and cases.result.get("requirement_count") == 2,
      "the result carries the counts the guide is built from", str(cases.result.keys()))


class Exploding(FakeMatcher):
    def match(self, *a, **k):
        raise RuntimeError("the matcher fell over")


times = FakeTimes()
run = Run(cases=FakeCases([]), corpus=FakeCorpus(), registry=FakeRegistry(),
          matcher=Exploding(), finder=FakeFinder(), builder=FakeBuilder(),
          detect_fn=lambda *a, **k: None, agreement_fn=lambda *a, **k: ("", ""),
          times=times, cvs=FakeCVs(None))
events = [json.loads(c.removeprefix("data: ").strip()) for c in run.stream(FakeCase())]
check(any(e.get("event") == "error" for e in events), "a run that dies says so on the stream")
check(times.recorded == [], "and a run that died is not evidence of how long a run takes")

print()
print("what the result page says you gave us")

from migragent.result_page import result_html  # noqa: E402


@dataclass
class ResultCase:
    jurisdiction: str = "CA"
    lane: str = "work"
    case_id: str = "case-1"
    created_at: str = "2026-08-31T00:00:00+00:00"


COVERAGE = {"score": 0, "covered": 0, "document_requirements": 115,
            "action_only": 15, "unverified": 0}
RESULT = {"routes": [], "form": {"questions": []},
          "requirement_count": 130, "source_count": 28}

html = result_html(ResultCase(), COVERAGE, RESULT, [], cv=FakeCV())
check("cv.pdf" in html, "the CV somebody uploaded is listed")
check("You did not upload anything" not in html,
      "and they are not told they gave us nothing")

html = result_html(ResultCase(), COVERAGE, RESULT, [], cv=None)
check("You did not upload anything" in html,
      "a case with nothing uploaded still says so")

html = result_html(ResultCase(), COVERAGE, RESULT, [FakeDoc("passport.pdf")], cv=None)
check("passport.pdf" in html and "You did not upload anything" not in html,
      "and documents are listed the way they always were")

print()
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
