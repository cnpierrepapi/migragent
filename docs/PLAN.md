# The plan

Four builds. Everything that has been asked for is in one of them. Each ends with something working
on a live URL.

Standing rules are in `docs/RULES.md`. What gets read and how is in `docs/SOURCES.md`. How it feels
to use is in `docs/HOW_IT_WORKS.md`. Every defect found so far is in `docs/DEFECTS.md`.

**Where it lives:** Cloud Run, service `migragent`, at `migragent.onenept.com`. Firestore, Pub/Sub,
Cloud Scheduler, Cloud Storage. The app holds passports and a service account, so nothing is exported
to another provider. A push to `main` deploys, and the job fails unless the new revision answers.

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
  Google agent framework is a mandatory requirement of the event, so this is the first thing built,
  ahead of everything below.

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
- **US and Australia come off the offer.** US federal immigration sites disallow us in robots.txt and
  Australia refuses our crawler outright. They are shown as **coming soon**, with the real reason
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

---

## Build 4 — The person, the board, and the work after arrival

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
- **It gets its own score: CV fit, per country.** Page limits, whether a photo or a date of birth is
  expected or a liability, Canadian versus British conventions, the French CV, where references belong.
- **Sourcing is split and labelled.** Where an official body publishes guidance it is cited like any
  requirement. Where it is convention rather than rule, it says so and does not borrow the guide's
  authority.
- **Rewriting is live in the product.** One CV per target country, and later one per application,
  because a CV for everything is a CV for nothing. Every rewrite is a draft and says so.

### Jobs, from shortage lists rather than from guesswork

"Companies that hire the most internationals" is not something anybody publishes, so building on it
means inferring a list and then citing ourselves for it. Shortage lists are published, official,
dated, and already the kind of page this pipeline reads. So the chain runs:

1. **Shortage list** for the country, read and quoted like any other government source.
2. **Listings** for those occupations, from public job services, under the same robots gate.
3. **Fit score** for the user against a listing, computed from their CV and their case.
4. **Notification**, routed the same way source changes are.

Two rules hold this together and both are the same rule that governs the guide.

- **A job posting is never a source for a requirement.** It is an opportunity. Requirements come from
  governments and regulators. A posting that says something about a visa is evidence of what an
  employer believes, not of what the law is, and it is labelled that way.
- **The fit score is a fit score.** It says this listing matches your profile, and it never says or
  implies you will get the job. That gets written on the screen next to the number, not buried.

Listings are watched by the same daily round as everything else, because a role that closed is worse
than no role at all.

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

## The three mandatory requirements

| Required | Where |
| --- | --- |
| Gemini 3.5 or newer | requirement extraction, document reading, diff explanation, CV fit, fit scoring |
| A Google agent framework | ADK, on the researcher and on the people finder |
| Google Cloud infrastructure | Cloud Run and Cloud Run jobs, Firestore, Pub/Sub, Cloud Scheduler, Cloud Storage |

No marks exist for touching more Google products. Every service above earns its place, and the
restraint gets said out loud, because what we deliberately did not use is more interesting to a judge
than a longer list.
