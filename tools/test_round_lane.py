"""Check the round consults the Lane Classifier before extracting, no network.

    python -m tools.test_round_lane

Three things, each of which would be silent if it broke:

  1. A depth 1 government page the classifier reads as another route is not
     extracted into this lane. The extractor is never called for it, and the
     round counts it as off-lane.
  2. A page the classifier confirms is extracted as normal.
  3. A classifier that could not answer does not block extraction. A second
     opinion being unavailable is not evidence against the first one.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from datetime import datetime, timezone  # noqa: E402

from migragent.extract import Extraction  # noqa: E402
from migragent.fetcher import Fetched  # noqa: E402
from migragent.registry import Source  # noqa: E402
from migragent.round import Round  # noqa: E402
from migragent.lanes import LaneVerdict  # noqa: E402

WORK_PAGE = (b"<html><body><h1>Skilled Worker visa</h1><p>You must have a "
             b"confirmation of sponsorship from an approved employer.</p></body></html>")


def _source(depth: int = 1, kind: str = "government") -> Source:
    return Source(source_id="uk-study-x", jurisdiction="UK", lane="study",
                  kind=kind, url="https://www.gov.uk/skilled-worker-visa",
                  title="skilled worker visa", language="en", provenance="official",
                  discovered_via="walk", lead_url="https://www.gov.uk/study",
                  depth=depth, robots_allowed=True)


class FakeRegistry:
    def __init__(self, source): self._s = source
    def for_lane(self, j, l): return [self._s]
    def put(self, s): pass
    def by_url(self, j, l, url): return None


class FakeCorpus:
    def __init__(self): self.recorded = []
    def has_been_read(self, sid): return False
    def live_ids_for_source(self, sid): return set()
    def record(self, sid, extraction, j, l):
        self.recorded.append(sid)
        class R: kept = len(extraction.requirements); dropped = 0
        return R()
    def retire(self, ids, at, why): return 0


class FakeSnapshots:
    def store(self, sid, page): return "snapshots/uk-study-x/1.html"
    def read(self, path): return None


class FakeFetcher:
    def permission(self, url): return "allowed", ""
    def fetch(self, url):
        return Fetched(url=url, outcome="fetched", read_at="2026-08-27T00:00:00+00:00",
                       status=200, body=WORK_PAGE, sha256="a", raw_sha256="b",
                       content_type="text/html", final_url=url)


class FakeExtractor:
    def __init__(self): self.calls = 0
    def extract(self, page, *, jurisdiction, lane, language, provenance):
        self.calls += 1
        from migragent.extract import Requirement
        return Extraction(source_url=page.url, read_at=page.read_at,
                          requirements=[Requirement(
                              text="You need sponsorship.", quote="x",
                              category="requirement", source_url=page.url,
                              read_at=page.read_at, source_language="en",
                              provenance="official", jurisdiction=jurisdiction,
                              lane=lane)],
                          open_questions=[])


class FakeClassifier:
    def __init__(self, verdict): self.verdict = verdict; self.calls = 0
    def classify(self, url, text):
        self.calls += 1
        return self.verdict


def _round(classifier, extractor, corpus, source):
    return Round(registry=FakeRegistry(source), corpus=corpus,
                 snapshots=FakeSnapshots(), fetcher=FakeFetcher(),
                 extractor=extractor, explainer=None, changes_writer=None,
                 lane_classifier=classifier)


def main() -> int:
    results: list[tuple[bool, str, str]] = []

    def check(ok, name, detail): results.append((bool(ok), name, detail))

    # 1. Classifier reads it as work; the lane is study.
    src = _source()
    ext = FakeExtractor()
    cor = FakeCorpus()
    off = LaneVerdict(lanes={"work"}, evidence={"work": "x"},
                      stopped_because="the agent marked the page and finished")
    r = _round(FakeClassifier(off), ext, cor, src)
    result = r.run("UK", "study", mode="extract")
    check(result.off_lane == 1 and result.extracted == 0,
          "a page read as another route is counted off-lane, not extracted",
          f"off_lane={result.off_lane}, extracted={result.extracted}")
    check(ext.calls == 0, "the extractor was never called for the off-lane page",
          f"extractor calls: {ext.calls}")
    check(cor.recorded == [], "nothing about it reached the corpus",
          f"corpus records: {cor.recorded}")

    # 2. Classifier confirms study.
    src = _source()
    ext = FakeExtractor()
    cor = FakeCorpus()
    ok_v = LaneVerdict(lanes={"study"}, evidence={"study": "x"},
                       stopped_because="done")
    r = _round(FakeClassifier(ok_v), ext, cor, src)
    result = r.run("UK", "study", mode="extract")
    check(result.extracted == 1 and result.off_lane == 0,
          "a confirmed page is extracted as normal",
          f"extracted={result.extracted}, off_lane={result.off_lane}")
    check(ext.calls == 1, "the extractor ran once", f"extractor calls: {ext.calls}")

    # 3. Classifier could not answer.
    src = _source()
    ext = FakeExtractor()
    cor = FakeCorpus()
    down = LaneVerdict(error="the second reader did not answer: 429")
    fc = FakeClassifier(down)
    r = _round(fc, ext, cor, src)
    result = r.run("UK", "study", mode="extract")
    check(fc.calls == 1 and ext.calls == 1 and result.extracted == 1,
          "a classifier that could not answer does not block extraction",
          f"classifier calls={fc.calls}, extractor calls={ext.calls}, "
          f"extracted={result.extracted}")

    # 4. Depth 0 entry pages are not lane-checked at all.
    src = _source(depth=0)
    ext = FakeExtractor()
    cor = FakeCorpus()
    fc = FakeClassifier(off)
    r = _round(fc, ext, cor, src)
    result = r.run("UK", "study", mode="extract")
    check(fc.calls == 0 and result.extracted == 1,
          "a depth 0 entry page is trusted and never sent to the classifier",
          f"classifier calls={fc.calls}, extracted={result.extracted}")

    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        print(f"        {detail}")
    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
