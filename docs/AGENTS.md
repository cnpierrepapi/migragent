# The agents

Build 7.3. This started as a plan for sixteen agents. Building the first five made the honest
number clear: **five have genuine agentic structure, and the other eleven are single model calls
that `verify.py`, `changes.py`, `coverage.py` and their neighbours already do well.** Wrapping the
eleven in `LlmAgent` for the count is exactly the padding `docs/DECISIONS.md` and the
people-finder-stays-not-an-agent call exist to refuse, so they are not wrapped. This document is
the design of record, and the section "Why not the other eleven" is part of it.

## The test for what becomes an agent

Sharper than the earlier "a decision or a loop already exists". An agent earns the name only if it
makes decisions **across multiple steps** about what to do next: navigate to another page, choose
a tool, or revise its own output after a check refused it. A single model call whose response is
then validated in code is a single model call, however many items are in the response.

Everything deterministic stays deterministic code, on purpose, because a rule an agent can decide
to skip is not a rule:

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
its one retry loop (D20). The agents do not get their own ideas about a 429. Gemini 3.5-flash
throughout.

## The five

All built, all behind a flag, all with a scripted-model test that traps ADK's own client.

| Agent | Multi-step structure | Replaces | File |
| --- | --- | --- | --- |
| **Researcher** | navigates: reads a page, sees its links, chooses which to open, decides when it has enough | the walker that read every link to depth one | `migragent/researcher.py` |
| **Scout** | explores from candidate URLs, follows a shell's links to the real content behind it | hand-maintained `tools/seed_registry.py` | `migragent/agents/scout.py` |
| **Extractor** | records a requirement, gets the quote check's refusal back in words, finds the real sentence or drops it | one-shot call in `extract.py` that drops a mis-copied quote silently | `migragent/agents/extractor.py` |
| **Lane Classifier** | marks each route with a page-checked sentence, retries a refused mark, decides "neither" | nothing: closes D29 and D32 | `migragent/agents/lane.py` |
| **Coverage Matcher** | proposes a match, gets back "that field was not uploaded", looks for another document that addresses the requirement | one-shot call in `coverage.py` that drops a wording-miss match silently | `migragent/agents/coverage.py` |

The Researcher and the Extractor navigate or revise over real text, which is where a second pass
genuinely recovers something. The Coverage Matcher is here because its output is the readiness
score, the number most likely to become a lie, and a recovered wording-miss is worth the extra
call. The Lane Classifier is the thinnest of the five and is here because it closes a shipped
defect nothing else catches.

## Why not the other eleven

Each was in the sixteen. Each is a single model call whose response is validated in code, with no
step where the model chooses what to do next. Making them agents would add a retry loop that
recovers little, because a dropped item is dropped when the evidence genuinely is not in the known
set.

| Not an agent | What it is | Why the call is enough |
| --- | --- | --- |
| **Verifier** | one YES/NO per requirement, Gemma | `verify.py` already does this, and `review()` loops in code. Nothing for the model to decide beyond the answer. |
| **Change Interpreter** | one sentence about a diff | `changes.py` `Explainer.explain`. One call, `material` flag, done. |
| **Translator** | extraction with a keep-the-original-sentence instruction | a mode of the Extractor's prompt, not a separate loop |
| **Attribution Verifier** | "is this page about the institution asked for" | one call; `schools.py` acts on the boolean |
| **Course / Document / CV Readers** | structured fields off one document | one call each; the cross-checks are code |
| **Route Finder** | options for one gap, cited to corpus ids | one call, then id validation. A dropped option cited a requirement we do not hold; retrying does not conjure one. |
| **Fit Scorer** | posting requirements matched to CV claims | one call, then quote-and-claim validation. Same shape as Route Finder. |
| **Digest Router** | embed a change, match to users, drop the already-told | embedding distance and a set difference. Barely a model call at all. |

If a judge counts nodes, the honest count is five `LlmAgent`s, plus the orchestration below, plus
the deterministic gate nodes. The restraint is the architecture story, the same way not using
Pub/Sub and not making the people finder an agent are.

## The former sixteen, for reference

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
agent added nothing. This refusal sits next to the eleven above, as the same kind of call: a
deliberate no.

## The orchestration layer

**SequentialAgent, two, over the five real agents and the deterministic gates:**

- `IngestionPipeline`: Scout, then `RobotsGate`, then fetch and hash and snapshot, then Extractor,
  then the Verifier call, then Lane Classifier, then `QuoteCheck`, then `CitationBinder`, then
  persist.
- `IntakePipeline`: the Document Reader call, then Coverage Matcher, then the Route Finder call
  over each gap.

The watch and work paths stay as they are: `Round` already sequences fetch, `MeaningGate`, the
Change Interpreter call and retire in `round.py`, and the work path sequences the reader, the
scorer and the drafts in `run.py`. Naming those `SequentialAgent` would wrap a sequence that is
already legible in code and add nothing a diagram cannot show.

**LoopAgent:** the Researcher's open-decide-repeat is a loop, and it is inside `researcher.py`
already. ADK's `LoopAgent` is a way to write that loop, not a new capability, so it is not
adopted just to have the node type.

**BaseAgent, four, non-LLM:** `RobotsGate`, `QuoteCheck`, `MeaningGate`, `CitationBinder`. The
deterministic law, sitting in the pipeline as its own node type so a reader of the graph sees
where judgment stops.

Five `LlmAgent`s, two `SequentialAgent`s, four `BaseAgent` gates. The number is small because the
work that is genuinely agentic is small, and saying so is worth more to a judge than a longer list.

## How it lands on the infrastructure

No new Google services. The research and watch pipelines run inside the existing `migragent-ingest`
Cloud Run job. The intake and work pipelines run inside web requests, exactly where the plain calls
run now.

Each agent is behind a flag, `MIGRAGENT_AGENT_<NAME>`, off by default. `IngestionPipeline` reuses
the `MIGRAGENT_RESEARCHER=agent` switch that is already there.

Rollout is lane by lane. Turn a pipeline on for one lane, run it twice with nothing expected to
change and demand a clean result, read the disagreements rather than the rate (D40), then widen.
Nothing here is allowed to make the live product worse on the way.

## State, 27 August 2026

Built, tested, flag-gated, pushed:

- `migragent/agents/base.py`: `run_to_completion`, lifted from `researcher.py`.
- Scout, Extractor, Lane Classifier, Coverage Matcher. The Researcher was already there.
- Lane Classifier wired into `round.py` at depth 1 and deeper; Extractor and Coverage Matcher
  swapped in by flag at their call sites.

Open:

1. The Lane Classifier costs a full agent session per page, which makes a 143-page watch round
   take hours. It needs a cheaper path before it runs on the daily round: a single classification
   call, or running only on pages the byte and text gates already flagged as new or changed.
2. `IngestionPipeline` and `IntakePipeline` as `SequentialAgent`s over the five agents and the
   four gate nodes.
3. `docs/ARCHITECTURE.md` diagram: five agents, two sequences, four gates, and the calls that are
   deliberately not agents.
4. Build 6: the video, the repo going public, the Devpost category.
