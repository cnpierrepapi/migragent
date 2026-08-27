# The agents

Build 7.3. Where there is one agent today, the researcher, there are sixteen, and every one of them
sits on a judgment call that is currently either a single unguarded model call or an open defect.

This document is the design of record. `docs/PLAN.md` Build 7.3 points here. `docs/DECISIONS.md`
gets one entry per agent naming the thing it closes, because that list is the defence against a
judge reading a count and seeing padding.

## The rule for what becomes an agent

Unchanged from `docs/PLAN.md`. An agent is added only where a decision or a loop already exists in
the code and is spelled out by hand today. Everything deterministic stays deterministic code, and it
stays that way on purpose, because a rule an agent can decide to skip is not a rule:

- the robots.txt gate
- fetch, the stable digest, the snapshot archive write
- the verbatim quote check, which is string containment against the page that was actually fetched
- the citation, built from the fetch, never passed through a model
- the `difflib` diff, the embedding distance, the modality multiset
- PDF rendering
- retirement, which is a set difference on live ids

These appear in the pipelines below as nodes of a different type, `BaseAgent` rather than `LlmAgent`,
so the architecture diagram shows the law sitting in the graph next to the judgment.

## Every model call still goes through one caller

`migragent/agent_llm.py` is the `BaseLlm` ADK drives, and underneath it is `migragent/model.py` with
its one retry loop (D20). Sixteen agents do not get sixteen ideas about a 429. Gemini 3.5-flash for
all of them except the Verifier, which is Gemma 4.

## The sixteen

Grouped by the pipeline they run in. "Replaces" is what does the job today.

### Research and ingestion

| Agent | Decides | Replaces | Closes |
| --- | --- | --- | --- |
| **Scout** | which entry pages are worth seeding for a jurisdiction and lane; walks the fallback chain (institution site, then course portal, then drop and take the next) | `tools/seed_registry.py`, hand-maintained | the Spain reseed, where the seeds were navigation shells and nobody noticed for days |
| **Researcher** | from an entry page, which links to open, when structure has run out, when it has enough | already an agent, `migragent/researcher.py` | unchanged |
| **Extractor** | reads one page and proposes requirements, each with a span copied from the page; survey then revise. Source-kind aware: government pages yield requirements, shortage lists yield occupations with the extra guard that the occupation title sits inside its own quote | `migragent/extract.py` and `migragent/occupations.py`, one call each | folds the shortage-list reader in rather than giving it its own agent |
| **Verifier** | given a page and a proposed requirement, and nothing else, whether the page states it | planned 7.2, `migragent/verify.py` | Gemini marking its own homework on text, the way `ocr.py` already refuses to on images |
| **Lane Classifier** | which lane or lanes a discovered page actually serves | nothing | D29 and D32: a discovered page inherits its finder's lane, government sites cross-link study and work, and a true sentence ends up filed under the wrong question |
| **Translator** | for a non-English page, which sentence is the original-language one the claim rests on, and whether the translation beside it is faithful | an instruction inside the extraction prompt | a translation error becoming an invented requirement with an official link next to it |
| **Change Interpreter** | given a diff that has already cleared the meaning gate, substantive or cosmetic, then writes the change record with the government's own sentence and the date attached | planned 7.3 | a watcher that cries change every morning until the reader stops looking |
| **Attribution Verifier** | whether a page proves it is about the institution that was asked for | a slug heuristic and a string check in `migragent/schools.py` | "University of Chicago Booth School of Business" resolving to the University of Chicago's page and storing its figure against a UK row |
| **Course Reader** | fees, intake dates and entry requirements from a course page, and whether a number on the page is actually the tuition | the course ingestion in `migragent/schools.py`, one call | fees existing for 146 of 3,990 courses because the number is usually behind a calculator, and telling a real fee from a deposit or an application charge |

### Profile and matching, the `/start` flow

| Agent | Decides | Replaces | Closes |
| --- | --- | --- | --- |
| **Document Reader** | for each uploaded document: its kind, the fields on it, the held qualification and its level and subject, and whether a name or date disagrees across two documents | `migragent/documents.py` and `migragent/level.py`, one call each | folds the level and subject reader in; the two read the same pixels |
| **Coverage Matcher** | which extracted requirements each uploaded document actually covers. This is the readiness score, the one number in the product that has to be true | `migragent/coverage.py`, one call | a progress bar that measures uploading instead of coverage |
| **Gap and Route Finder** | for each gap, the accepted alternatives, their cost and their lead time, and which ones this regulator actually accepts. A loop over gaps | `migragent/routes.py` and `migragent/gaps.py` | the 2:2 case, which has to produce real routes rather than a dead end |

### Work and post-arrival, `/work` and `/board`

| Agent | Decides | Replaces | Closes |
| --- | --- | --- | --- |
| **CV Reader** | what the CV can be shown to say, and nothing it cannot | `migragent/cv.py`, one call | a rewrite that borrows the guide's authority for a claim the person never made |
| **Application Writer** | the country-shaped CV clone, the per-listing rewrite, and the cover letter. Three modes, one guard: every claim traces to the CV, and every number is checked against the numbers in the CV | `migragent/drafts.py`, three functions | folds the CV localiser, the cover letter drafter and the per-listing rewriter into one role, because they are one role |
| **Fit Scorer** | the share of a posting's stated wants the CV can evidence, each row showing the posting's own sentence beside the person's own line. A loop over what the posting asks for | `migragent/fit.py` | "a welder was shown two jobs out of two thousand", and a score that reads as a verdict on the person rather than a match against one advert |

### Notification

| Agent | Decides | Replaces | Closes |
| --- | --- | --- | --- |
| **Digest Router** | which users a change reaches, by embedding it against their guide, and which of them have already been told so they are not told twice | `migragent/alerts.py` | running every source against every user, and telling somebody the same thing on Tuesday that they read on Monday |

### Merged away or erased

- **Shortage-list Reader**: merged into the Extractor, which now dispatches on `source.kind`. `round.py`
  already routes government pages and shortage lists down separate paths; the agent inherits that.
- **Level and Subject Reader**: merged into the Document Reader. Level and subject are more fields off
  the same documents, read in the pass that already checks for a cross-document mismatch.
- **CV Localiser, Cover Letter Drafter, CV Rewriter**: merged into one Application Writer. All three
  generate an application document from CV claims under the same number check.
- **Form Builder**: erased. `migragent/form.py` already serves it. Once the Gap and Route Finder knows
  what is missing, the fillable form is a deterministic assembly of that plus the known case fields.
  No judgment is left.

## Kept deliberately not an agent

**People Finder.** `migragent/people.py`, Google Search grounding and one structuring call.
Decision 9 stands: grounding and a tool-calling loop solve different halves of that problem and the
agent added nothing. This refusal stays on the record next to sixteen agents, because it is what
makes the sixteen read as engineering rather than as a number being farmed.

## The orchestration layer

Twelve nodes, so the graph reads the way SalesShortcut's did.

**SequentialAgent, five:**

- `IngestionPipeline`: Scout, then RobotsGate, then fetch and hash and snapshot, then Extractor,
  then Verifier, then Lane Classifier, then QuoteCheck, then CitationBinder, then persist.
- `WatchPipeline`: fetch, then MeaningGate, then Change Interpreter, then retire, then Digest Router.
- `IntakePipeline`: Document Reader, then Coverage Matcher, then Gap and Route Finder.
- `WorkPipeline`: CV Reader, then Application Writer in clone mode, then listings match, then Fit
  Scorer. `docs/PLAN.md` already says this one becomes a SequentialAgent because it is one.
- `ApplicationPipeline`, per board item: Fit Scorer, then Application Writer in rewrite mode, then
  Application Writer in cover-letter mode.

**ParallelAgent, one:**

- `LaneFanout`: runs `IngestionPipeline` across lanes at once, which maps onto the Cloud Run job's
  existing ten tasks at parallelism five. One request per host at a time is still held in code.

**LoopAgent, two:**

- `ResearchLoop`: the Researcher's open, decide, repeat until enough. The loop that is already there,
  named.
- `GapLoop`: iterate the gaps until each has at least one route or is marked unresolvable.

**BaseAgent, four, non-LLM:** `RobotsGate`, `QuoteCheck`, `MeaningGate`, `CitationBinder`. The
deterministic law, sitting in the graph as its own node type.

Sixteen plus twelve is twenty-eight nodes.

## How it lands on the infrastructure

No new Google services. The research and watch pipelines run inside the existing `migragent-ingest`
Cloud Run job. The intake and work pipelines run inside web requests, exactly where the plain calls
run now.

Each agent is behind a flag, `MIGRAGENT_AGENT_<NAME>`, off by default. `IngestionPipeline` reuses
the `MIGRAGENT_RESEARCHER=agent` switch that is already there.

Rollout is lane by lane. Turn a pipeline on for one lane, run it twice with nothing expected to
change and demand a clean result, read the disagreements rather than the rate (D40), then widen.
Nothing here is allowed to make the live product worse on the way.

## Build order

1. `migragent/agents/base.py`: the run helper, extracted from `researcher.py`, so every agent reuses
   the thread, the event loop and the turn counting instead of copying them.
2. `IngestionPipeline` end to end on UK study. This is the video's opening shot.
3. `WatchPipeline`. Also unblocks the meaning gate's first real watch round.
4. `IntakePipeline`, then `WorkPipeline`, then `ApplicationPipeline`.
5. `docs/PLAN.md`, `docs/ARCHITECTURE.md` diagram, `docs/DECISIONS.md`.
