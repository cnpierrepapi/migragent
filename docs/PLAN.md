# The plan

Six builds. Each one ends with something working on a live URL.

**All six are built.** What is left is not a build, it is the submission: the video, the repo going
public, and a category. Plus a long tail of countries with a visa guide and no school or job data,
which is a data problem rather than a code one.

Standing rules are in `docs/RULES.md`. What gets read and how is in `docs/SOURCES.md`. How it feels
to use is in `docs/HOW_IT_WORKS.md`. Every defect is in `docs/DEFECTS.md`, and the ADK ones worth
sending upstream are split out into `docs/ADK_FINDINGS.md`.

**Where it lives:** Cloud Run, service `migragent`, live at `https://migragent.onenept.com` with a
Google Trust Services cert. Firestore, Cloud Scheduler, Cloud Storage, Cloud Vision for OCR.
No Pub/Sub: Cloud Run already numbers its own tasks, so the topic would have been a delivery
mechanism with nothing to deliver. A push to `main` deploys the service. The ingest job is deployed
by hand on purpose, because letting CI update it would mean granting the deploy identity the right
to act as the watcher, and nothing is allowed to become the watcher. That is D38.

**What runs on a schedule:** retention sweep 03:17, watch round 04:40, job listings 05:00, digest
05:20, all UTC. The order is load bearing. Read the government pages, ask the boards, then tell
people.

**Words used throughout.** The **registry** is the list of pages we have decided to read, one row per
page. The **corpus** is what we got out of those pages: the requirements themselves, each with its
quote, its link and the date it was read. Growing the registry means finding more pages worth
reading. Growing the corpus means actually reading them. The two numbers move independently and the
product shows both, because a large registry with a thin corpus is a promise, not an answer.

---

## Where the pipeline actually is

Measured on 19 August 2026, not remembered.

| Stage | Built | State |
| --- | --- | --- |
| Seed the registry | yes | 16 entry pages |
| Walk out from the entry pages | yes | 1,046 rows, all government, all official |
| Robots gate, fetch, hash, snapshot | yes | 179 snapshots in Cloud Storage |
| Extract requirements with a verified quote | yes | ran over 56 pages |
| Corpus | yes | 708 requirements, in two lanes only |
| Guide and PDF | yes | live |
| Documents, coverage, routes, fillable form | yes | live |
| **Re-read a source and diff it** | **no** | nothing compares today against yesterday |
| **Explain what moved** | **no** | |
| **Daily schedule for ingestion** | **no** | the only scheduled job deletes expired cases |
| **Pub/Sub fan-out** | **no** | zero topics exist |
| **Run ingestion off a laptop** | **no** | tools only, one terminal, no retry, no logs after |

Two facts follow from that table and they are the whole of Build 3.

**Every source in the registry was read once, on 18 August 2026, and nothing has read one since.**
The snapshot machinery was written to be diffed against and nothing is diffing it. Every "read on"
date in the product is the date a person ran a tool by hand.

**Ingestion has never run anywhere except a laptop.** That is why the shell runs kept failing. A run
over hundreds of pages outlives a terminal window, dies with it, has no retry when one host blips,
and leaves no log anybody can read afterwards. It is also why only two lanes are deep: not a design
decision, a run that could not survive long enough. The fix is not a better script.

---

## Build 1 — The guide, end to end

**Ends with:** answer two questions on the live URL, get a PDF with real requirements and real
citations. **Done.**

**Foundation**
- Least privilege roles on `migragent-researcher`, `migragent-writer`, `migragent-watcher`,
  `migragent-web`, and a test that shows the researcher refused a write. Closes D1.
- Cloud Run service, deploy path, `/health`, domain mapping to `migragent.onenept.com`.

**The registry, as data**
- Firestore collection, one row per source. Row carries URL, language, discovery, robots state, last
  read, hash, snapshot location, provenance.

**The reader**
- Fetcher in plain code: robots.txt gate, fetch, hash, snapshot to Cloud Storage, stamp the date
  read. Identifies itself, one request per host at a time, backs off.
- Extraction with Gemini. Every requirement carries a verbatim quote checked against the page before
  it is allowed to exist. The citation is attached from the fetch and never passes through the model.
- Translation path: extract from the original language, keep the original sentence verbatim, store
  the translation as a translation.

**Still open in Build 1**
- **The researcher is not on ADK.** Gemini is called over plain HTTP from `migragent/model.py`. A
  Google agent framework is mandatory, and it is Build 4.

---

## Build 2 — Documents, the score, and the fillable form

**Ends with:** uploading a transcript changes the guide, moves a real number, and returns a form
built for your case. **Done, apart from the CV work now moved to Build 4.**

**Uploads**
- Passport, transcript, degree, English test, registration, employment letters.
- Gemini reads them. This is the multimodal work.
- Data protection from the start: stated retention window, encryption, a delete-my-data path that
  actually deletes, and a sweep on a schedule that proves the window is kept.

**The score**
- Coverage matching: which extracted requirements each uploaded document actually addresses.
- The readiness score is that coverage, not the upload count. Tapping it opens the breakdown.
- Documents listed by what they are worth, because a passport unlocks more than a school transcript.
- Threshold crossing fires the confetti and lights **GO**. Nothing fires under reduced motion.

**Gaps and routes**
- What is satisfied, what is missing, what is expiring.
- Every gap gets routes: accepted alternatives, cost, booking lead time, and which ones this
  regulator actually accepts.

**The fillable form**
- Generated per case, asking only what is still unknown now that the lane and the gaps are known.

---

## Build 3 — Ingestion that runs itself

**Ends with:** every offered lane is deep, a daily round re-reads the sources without anybody
starting it, and a real change is caught, dated and explained.

This is the build that turns a set of tools into a pipeline. Nothing else in the product improves
until it exists, because everything downstream is only as current as the last hand run.

### The ingestion job

- One **Cloud Run job**, two modes. `extract` reads pages that have never been read. `watch` re-reads
  pages that have, and diffs them. Same fetcher, same robots gate, same quote check, same snapshot
  archive, so the two modes cannot drift apart in what they will accept.
- **Cloud Scheduler fires, Pub/Sub fans out, one message per lane, the job runs per message.** Lanes
  run in parallel because they are different hosts. Within a lane it stays one request per host at a
  time, so parallelism never turns into hammering somebody's government website.
- A message that fails is retried by Pub/Sub rather than lost. A page that fails is recorded and the
  run continues, which is D18 and already how the tools behave.
- Every round writes a row saying what it read, what it skipped, what changed and how long it took.
  A pipeline nobody can audit afterwards is a pipeline that can quietly stop.

### Hash first

- Byte identical page stops there. No model call, no cost.
- The comparison uses the **stable** digest, not the raw bytes, because canada.ca returns different
  bytes on every single fetch and a naive hash would have fired on every page every day forever.
  That is D6 and it is the difference between a daily round that costs pennies and one that bills for
  the whole corpus nightly.

### On a change

- Diff the two versions. Gemini explains what moved, in a sentence.
- Both versions, both dates and the source are recorded. The old snapshot is not overwritten, because
  the archive is append only and that is the only way "it changed on this date" can be shown rather
  than asserted.
- **No run is ever backdated.** The change line is seeded from the government's own published change
  history, carrying their dates and their sources, and every round we run carries the date it really
  ran. Direction is reported as an observation of changes already published, never as a forecast.

### Turning "registry only" into deep

- Extraction runs over every offered lane, not two. Guide citable depth stays 0 and 1, which is the
  entry page and what the government links directly; depth 2 stays in the registry and stays watched.
- **US and Australia come off the offer**, and the reason is not the one first recorded. Neither
  disallows us. US immigration hosts refuse to serve their robots.txt to anybody, so we cannot learn
  their rules; Australia serves its robots.txt to a generic client and refuses it to one that says who
  it is. In both cases we stop, because a host that will not state its rules has not given permission. They are shown as **coming soon**, with the real reason
  written on the screen, and their rows stay in the registry marked blocked. They are not counted as
  readable and they do not quietly vanish, because a source that disappears from the count is how a
  count starts lying.
- That leaves ten offered lanes: UK, Canada, France, Spain and UAE, work and study each.

### Making the warehouse worth its name

The registry today is 1,046 government pages and nothing else. Three kinds of source are missing and
each one is a row type, not a code change.

- **Institutions.** Ranked by percentage of international students, top fifty per jurisdiction, or the
  top ten per cent of every registered institution where there are not fifty to take. Publisher and
  data year on every row, walking back from 2025 until real data exists. Three step route to a
  readable page: the institution's own site, then the course portal page, then drop it and take the
  next one down, with the drop recorded and the step that failed named.
- **Shortage lists.** Every target country publishes one under a different name, and they are
  government pages, so they arrive with a publisher and a date and go through the same quote check as
  everything else. The current name and URL for each country is something the registry establishes;
  it is not something anybody recalls.
- **Public job services.** Government run job boards, which are public by design. The large commercial
  boards disallow crawling and the robots gate is not negotiable, so they are out.

### The listings engine

Ingestion only. What a user sees built on top of this is Build 5.

- Shortage list read like any government page, so the occupations arrive quoted, linked and dated.
- Occupations become search terms against the public job services for that country. Listings are
  stored as their own row type, with employer, occupation, location, the listing URL, the date read
  and the date it closes if it says.
- **Listings are watched by the same daily round as everything else**, because a role that closed is
  worse than no role at all. A listing that stops resolving is marked closed on the date it stopped,
  not deleted, so the board can tell somebody the thing they were working on is gone.
- Coverage is reported per country rather than assumed. Most target countries run a public job
  service. The UAE most likely does not, and where a country has no readable service the product says
  so on screen rather than looking uniformly capable.

### What ships on screen at the end of Build 3

- **Every offered lane deep.** Ten lanes with real requirements, not two.
- **US and Australia shown as coming soon**, with the real reason written next to them.
- **Changes reach a person through their own case, and there is no general watch screen.**
  Earlier drafts of this plan had a browsable country page showing where policy loosened and where it
  tightened. That is a directory, and rule 39 says the product shows you things because of what you
  uploaded and filled in, for no other reason. A screen anybody can browse without a case is the same
  thing as a search box wearing a different hat.
  So an observed change surfaces on **your** guide, against **your** requirement, saying what moved,
  on what date, with both versions and the source. If it does not touch your case you never see it.
- The live counts on the front of the product move from a registry that is only read by hand to one
  that is read every day.

---

## Build 4 — The researcher on ADK

**Ends with:** the daily round is run by an agent that chooses what to read, and the mandatory
framework is satisfied by something that does real work rather than by a wrapper.

- The researcher becomes an ADK agent inside the ingestion job, with a small set of declared tools:
  fetch a page, check that a sentence really appears on it, record a requirement, look at a sibling
  page. It decides which pages to read and when it has enough.
- **What stays plain code, deliberately:** the robots gate, fetching, hashing, snapshotting, the
  verbatim quote check, the citation built from the fetch, PDF rendering. Those are rules rather than
  judgment, and a rule an agent can decide to skip is not a rule. This restraint gets said out loud in
  the submission.
- **The one thing that must not break:** ADK brings its own model client, which would route around the
  single caller in `migragent/model.py` and lose the retry and the status codes that D20 exists to
  preserve. Model calls stay behind that caller, and this is checked rather than assumed.
- Same agent, same tools, later reused by the people finder in Build 5.

**Where it is.** The agent, its tools and the model adapter are built:
`migragent/researcher.py` holds the desk the agent works at and the five tools it may use,
`migragent/agent_llm.py` puts ADK's traffic through `migragent/model.py`, and `tools/test_agent.py`
runs a whole session against a scripted model and a fake fetcher with ADK's own client booby
trapped, reporting 11 checks. The round hands entry pages to it behind `--agent` locally and
`MIGRAGENT_RESEARCHER=agent` on the job, off by default, and pages the agent chooses get registry
rows so tomorrow's watch round re-reads them. The reasoning is Decision 7.

**What it is worth, measured rather than asserted.** On `gov.uk/skilled-worker-visa` the agent
opened the pages about the job, English, costs and documents, and returned the salary floor of
£41,700, level B2, the three month deadline on a certificate of sponsorship, the Ecctis assessment,
the Care Quality Commission condition and the actual fees. The one shot extractor over the same
entry page returned "you must pay the application fee" with no amount. Same model, same page budget
per page, different choice of pages.

**Measured on 23 August 2026, and the answer was not the one the build expected.**
`tools/compare_agent.py` ran on two lanes, writing nothing. On UK work, where the walk holds 174
requirements from 19 pages, the agent read 3 pages and returned 26, of which 10 were things the walk
had missed including the actual fees. On Germany study, where the walk holds 26 from 4 pages, the
agent read 7 and returned 29, and 4 of those pages were not in the registry at all. So the daily
round is not handed to it: `MIGRAGENT_RESEARCHER` stays unset where the walk is deep, and the agent
runs as a second pass where the corpus says a lane is thin. Decision 10 has the numbers and the
reason the two lanes disagree.

---

## Build 5 — The person, the board, and the work after arrival

**Where it is, measured on 20 August 2026.** The work half is built and running end to end: 2,042
Canadian listings from Job Bank, filed under the 91 occupations Canada published as short; a CV
reader that keeps only what the document can be shown to say; a fit score computed from a posting's
own words; and a board that only a person moves. `tools/test_work.py` walks the whole chain against
the real model, the real store and a real posting, and deletes its case afterwards.

**The people finder is built**, on Google Search grounding rather than on our own crawl, which was
the user's call over my recommendation and is Decision 9. It carries three guards earned from its
first real run, and everything it returns is labelled as found by search rather than read by us.

**Still to do in this build:** the sign-in screen, which is blocked on an OAuth client, and
notification routing, which needs accounts before it means anything. The server half of accounts is
built: `migragent/accounts.py` verifies a Firebase ID token and claims a case for the person who was
already working on it.

**Ends with:** an account that remembers you, a board that fills itself, and a reason to still be here
next month.

### Accounts and memory

- Firebase Auth.
- Per user in Firestore: case, documents, guide, watchlist, and what they have already been told, so
  they are not told the same thing twice.

### Notifications

- Changes routed to the users they affect with embeddings and vector search, rather than running every
  source against every user.
- Browser push permission asked for properly, fired when a guide moves.

### The CV

The CV is a document like the others in that it gets uploaded and read, and unlike the others in every
way that matters, so it gets its own treatment.

- **It does not feed the readiness score.** Readiness is defined as the share of extracted requirements
  your documents cover, and a CV covers almost none of them. Letting it move that number would make
  the one honest number in the product dishonest.
- **Its score is fit against a listing.** Not a standalone grade for the document, and not a guess at
  a country's taste. A CV scores against a specific job, computed from the listing's own words and the
  user's case, and the number only exists where there is a listing to score it against.
- **The score says fit and never says you will get the job.** That sentence sits next to the number,
  not in a footnote. It means this listing matches your profile, which is a claim we can support, and
  nothing about an employer's decision, which is not.
- **Rewriting is live in the product.** One CV per target country to start, then one per listing,
  because a CV for everything is a CV for nothing. Country conventions are cited where an official
  body publishes them and labelled as convention where they are not, so the rewrite never borrows the
  guide's authority. Every rewrite is a draft and says so.

### Jobs, from shortage lists rather than from guesswork

"Companies that hire the most internationals" is not something anybody publishes, so building on it
means inferring a list and then citing ourselves for it. Shortage lists are published, official,
dated, and already the kind of page this pipeline reads.

Build 3 does the reading. Build 5 is what the user gets from it:

1. **Fit score** for the user against a listing, computed from their CV and their case.
2. **Notification**, routed the same way source changes are.
3. **I'm interested**, which is the next section.

**A job posting is never a source for a requirement.** It is an opportunity. Requirements come from
governments and regulators. A posting that says something about a visa is evidence of what an employer
believes, not of what the law is, and it is labelled that way wherever it appears.

### "I'm interested", and the board

Clicking **I'm interested** on a listing creates an item on the user's activity board, a kanban the
guide's steps already feed into. The item carries the work the application actually needs:

- the form to fill,
- the CV, rewritten for that listing,
- the cover letter, drafted,
- **the people worth speaking to**, which is the part nobody else does.

That last one is ported from `dossier`, which already does exactly this for companies: an agent loops
over search and page reads until it has enough, then returns a structured brief naming decision makers
and why they matter. Two things change on the way across. It becomes Python on ADK and Gemini rather
than TypeScript, since the framework is mandatory here and this is a genuine second place it earns its
keep. And it stays inside the same limits as the rest of the crawl: publicly published people in their
professional capacity, named by role and why they are relevant, found through search and public pages
rather than through anything that disallows us. No contact details are harvested and none are stored.

**Nothing is ever ticked off on the user's behalf, and every draft says it is a draft.** The user sends
the application. The board is the record of what they did, not a claim about what we did for them.

**This is the retention feature.** The guide ends when they land. The board does not, because everybody
is always looking for the next job, and the shortage lists and the listings keep moving whether or not
anybody is watching them.

---

## Build 7 — the second reader, and the agents that earn the name

**Written 24 August, after Build 6 was already planned. It runs before Build 6, because the
submission films whatever exists on the day.**

**Ends with:** a requirement that two independent models agree on, a watcher that stops crying
change when a page was only reworded, and four agents where today there is one, each with a written
reason for being an agent and one written reason for not being one.

### Why a second model at all

The strongest paragraph in this codebase is in `migragent/ocr.py`, and it is about not letting a
model mark its own homework. Gemini could transcribe a document and then check its own claims
against its own transcription, and a hallucinated date would verify itself. So Cloud Vision reads
the pixels instead: a different engine, no stake in the answer, and when the two agree that
agreement is worth something.

That argument does not stop at images.

Today the quote check is a string containment test against the fetched page, which is deterministic
and stays exactly as it is. But the judgement of whether a page *states* a requirement is Gemini's
alone, and nothing independent ever disagrees with it. A second reader closes that.

**Cloud Vision is already integrated and has never been claimed.** `migragent/ocr.py` posts to
`vision.googleapis.com`. It belongs in the mandatory-requirements table, which currently lists only
Gemini under models and is therefore wrong about what this thing runs on.

### 7.1 Gemma as the second reader

Gemma sees the page text and the proposed requirement. Nothing else. No prompt history, no tools,
no idea what Gemini decided or why. It answers one question: does this page state this.

- Both agree, the requirement is live.
- They disagree, it goes to open questions with both readings recorded.
- Gemma is unreachable, the requirement is live and flagged `unverified_second_read`, because a
  second opinion being unavailable is not evidence against the first one.

The disagreement rate is the number worth watching. If it is near zero the check is theatre and
should be said to be theatre. If it is high, one of the two readers is wrong often and we want to
know that before a user does.

**Runs on the ingestion path only, never on a web request.** A person waiting on a page does not
wait twice.

### 7.2 An embedding model, and D23 one storey up

D23 is closed at the byte layer: a page whose bytes moved but whose words did not no longer counts
as a change. The words layer is still crude. Any line that moved fires a full re-extraction and
writes a change row, so "you must" becoming "applicants must" reports as immigration policy moving.

That is D23's own warning arriving a level higher. A watcher that cries change every day teaches the
person receiving it to ignore it, and the day something real moves they ignore that too.

So: embed the old text and the new, compare, and let a reworded page settle without firing. A
changed number, a changed deadline, a changed fee still fires, because those move the meaning and
the distance shows it.

**The test is the one D23 taught:** run the round twice with nothing expected to change and demand a
zero, then run it against a page edited only cosmetically and demand a zero again, then change one
fee and demand exactly one.

### 7.3 The agents

**Full design is in `docs/AGENTS.md`.** It started as sixteen. Building the first five settled the
honest number: **five agents have genuine agentic structure**, meaning the model decides across
multiple steps what to do next. The other eleven are single model calls whose response is validated
in code, and `verify.py`, `changes.py`, `coverage.py` and their neighbours already do them well.
Wrapping the eleven in `LlmAgent` for the count is the padding this document exists to refuse.

The five: **Researcher** (navigates), **Scout** (explores from candidates), **Extractor**
(records, gets the quote check's refusal back, revises), **Lane Classifier** (marks routes, retries,
decides neither; closes D29 and D32), **Coverage Matcher** (proposes a match, gets back "not
uploaded", looks again; guards the readiness score). Orchestration: two SequentialAgents over those
five and four non-LLM BaseAgent gate nodes.

**The people finder stays not an agent** (Decision 9), and now sits next to eleven other calls that
are deliberately not agents. The restraint is the architecture story.

### Where this is cheap, and why

Every model call in this system goes through `migragent/model.py`. D20 forced that when one rate
limit produced three symptoms that looked like three unrelated bugs, and `tools/test_agent.py` fails
loudly if any caller ever escapes it again.

So a second model is a routing decision inside one file. Not a rewrite. The cost of D20 is being
repaid here.

### Order of work, and what survives being cut

1. Vision claimed in the requirements table. One sentence, and it is true today.
2. Gemma on the verifier. **Stands alone if everything after this is cut.**
3. Embeddings on the watcher.
4. The agent revamp.

Nothing here is allowed to make the live product worse. Each step ships behind a flag, off by
default, and turns on only after the round has run clean twice.

## Build 6 — The submission

**Ends with:** somebody who has never seen this can understand it, run it, and watch it work.

- **Architecture diagram**, showing the four identities, what each one may touch, and where the model
  is and is not allowed to be.
- **README a stranger can follow**, with the pre-existing code disclosed, which the rules require.
- **The video.** The beat that matters is an invented requirement being refused on screen. Every entry
  will show a thing being generated. Almost none will show a thing being rejected.
- Repo made public, domain mapped, category selected.

---

## The three mandatory requirements

Checked against the code on 24 August 2026, not remembered.

| Required | Where |
| --- | --- |
| Gemini 3.5 or newer | requirement extraction, document reading, CV reading, diff explanation, fit scoring, CV and cover letter drafts, the people finder |
| A Google agent framework | ADK, on the researcher: `migragent/researcher.py` and `migragent/agent_llm.py`. **Nowhere else.** The people finder was going to be the second one and is not: it is two plain Gemini calls, one of them with Google Search grounding, because grounding and a tool-calling agent solve different halves of that problem and the agent added nothing. |
| A second model, independent of Gemini | **Cloud Vision**, on the OCR check in `migragent/ocr.py`. Shipping since Build 2 and missing from this table until 24 Aug, which made the table wrong about what this runs on. It is here because a model checking its own transcription proves nothing, and a different engine reading the pixels does. |
| Google Cloud infrastructure | Cloud Run, Cloud Run jobs, Firestore, Cloud Scheduler, Cloud Storage, Vertex AI, Artifact Registry, Cloud Build, Identity Platform. **Not Pub/Sub**, which was in this table for weeks after Decision 4 removed it. |

Every service above earns its place, and the restraint gets said out loud, because what we
deliberately did not use is more interesting to a judge than a longer list. That still holds after
Build 7: Gemma and the embedding model arrive because a second reader and a reworded-page test need
them, and **Veo and Lyria stay out because nothing here needs video or music** and inventing a use
for them would cost more credibility than the 0.2 is worth.
