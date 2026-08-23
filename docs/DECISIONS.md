# Decisions, and what they cost

One entry per decision that would be expensive to reverse or easy to misread later. Written when the
decision is made, including the ones that turned out to be partly wrong.

---

## 1. Worker isolation: mostly carried from the deleted build, and over-invested in

**Decided:** 18 August 2026. **Revisited the same day**, after a fair challenge: is this useful here
or is it baggage?

**The honest answer is that it is mostly baggage, and one part of it is load-bearing.**

`identity.py` came across from the previous build along with the reasoning behind it. That build was
an enterprise data governance platform, where "which principal wrote this row" was close to the
product. Here it is not. This product's claim is about evidence, not about access control, and
nobody choosing whether to trust a study permit guide is going to ask which service account wrote it.

Scored honestly, one at a time:

**Append-only snapshot archive. Keep, and it earns its place.** The whole product rests on "we read
this page on this date, and here it is". The archive is that evidence. If the process that fills it
can also rewrite it, the archive is worth no more than the process, and the citation becomes a
promise again instead of a receipt. The researcher gets Forbidden 403 on read, overwrite, delete and
list, which was measured. This one is genuinely about what MIGRAGENT sells.

**The researcher cannot write to Firestore. Keep, but it is ordinary hygiene.** It means a bug in
extraction cannot corrupt the guide store. That is worth having and it cost one word in a script,
`datastore.viewer` instead of `datastore.user`. It is not a differentiator and should not be
described as one.

**Web cannot start a crawl round, and cannot call a model directly. Keep, small.** Stops a request
handler from being able to hammer government sites or run up inference. Sensible, cheap, minor.

**What was wrong was the attention, not the decision.** The roles are four lines of a shell script
and the test is one file. What actually happened is that a whole task got built around proving it,
because the claim in the inherited docstring was false and that had to be fixed. That fix was
necessary. Treating the result as a headline feature was not.

**What this changes going forward.** The isolation stays, because it is already there and costs
nothing to keep, and `tools/test_isolation.py` stays in the loop because a claim in the code has to
keep being true. It does not get more time, it does not lead the README, and it is not what the
demo opens on. The demo opens on the run.

**What it would have cost to get this wrong the other way:** shipping the inherited docstring
unchanged, asserting an isolation guarantee that was false. That is D1, and it is why the work was
not wasted even though the emphasis was.

---

## 2. Discovery is structural, never vocabulary

**Decided:** 18 August 2026, after two failures.

Deciding which pages to read cannot depend on matching words like "visa" or "fees" in a URL or link
text. That is a heuristic over names, it looks like understanding and is not, and it is already
recorded in `INHERITED.md` as the mistake that reported survey answers as decisions about people.

The first structural attempt was also wrong, and wrong measurably: same host plus section path plus
direct links kept 55 of 68 links on gov.uk, almost all of it global navigation. See D10.

**What works is that navigation appears on every page of a site and content does not.** Intersecting
the links of two pages from the same host isolates what makes a page different from its neighbours.
gov.uk goes from 68 links to 26; canada.ca from 43 to 10, leaving eligibility, get-documents,
prepare and apply.

**The cost of this choice:** a host needs at least two known pages before anything on it can be
walked. Hosts with a single entry point are skipped and the run says so, rather than returning
everything or nothing and calling it a result.

**No model takes any part in choosing what to read.** A model reads a page afterwards to say what a
requirement is. Which pages exist, and which were read, and when, stays plain code all the way
through, because that is the part that has to be checkable.

---

## 3. A model may say what a requirement means, never that one exists

**Decided:** 18 August 2026, building `migragent/extract.py`.

Two different failures hide under "the model made it up", and only one of them was covered.

**Invented sources** are handled structurally. The citation is assembled from the `Fetched` object,
the URL that was actually requested and the timestamp taken from the clock when the bytes arrived.
Neither ever enters a prompt or comes back out of a response, so no arrangement of words from a
model can produce a source that was not fetched.

**Invented requirements** are the likelier failure and were not covered at all. A model that has
read a thousand immigration pages will tell you a study permit needs a police certificate whether or
not the page in front of it says so, and it will be right often enough to be believed.

**So every requirement must carry a verbatim quote, and every quote is checked against the page text
before the requirement is allowed to exist.** No match, no requirement.

**Tested in both directions**, because a check that only ever accepts is not a check:

| given | verdict |
| --- | --- |
| a real quote from the page | accepted |
| the same quote with curly apostrophes and odd spacing | accepted |
| a plausible invented requirement | rejected |
| a real sentence with one number changed | rejected |
| two real fragments stitched together | rejected |

The middle row matters as much as the rest. Comparison folds whitespace, quote marks and dashes, so
a true quote is not thrown away over a curly apostrophe, which would make the check look stricter
than it is while quietly losing good requirements. Case and accents are kept, because they carry
meaning in French and Spanish.

**What this costs.** Anything the page implies but never states is lost. That is the intended trade,
and the implied things are exactly what "open questions" at the back of the guide is for.

**Dropped requirements are returned and reported, never swallowed.** A run that drops nine of ten
has to say so, because a silent drop rate is how a check like this stops being a check.

---

## 4. Pub/Sub was planned into the pipeline and then left out

**Decided:** 19 August 2026, while building the ingestion job.

The plan said Cloud Scheduler to Pub/Sub to a Cloud Run job, fanning out one message per lane. The
topic was written into the plan twice and into the memory of this project three times before anybody
asked what it was carrying.

**It was carrying an integer.** Cloud Run jobs already number their own parallel tasks and hand each
one `CLOUD_RUN_TASK_INDEX`. The runtime already retries a task that fails, already reports which
tasks died, and already limits how many run at once. A topic would have added a second thing to
configure, a second identity to grant, a second subscription to get wrong, and a second place for a
message to disappear, in order to deliver a number the platform hands over for free.

**So there is no Pub/Sub in this build.** The fan-out is `--tasks 10` and a fixed list of lanes,
where index 3 means the same lane on every run because the list is a list rather than a set.

**What it costs.** A topic would let something other than the schedule start a round, which is
exactly what we do not want: the whole isolation argument is that a web request cannot start a crawl.
It would also decouple the trigger from the work, which matters when the work is spiky and unrelated
to the trigger. Ingestion is neither.

**Why this is written down rather than left as an absence.** The mandatory requirement is one Google
Cloud service and this build uses five. There are no marks for a sixth, and a judge who sees a topic
with one publisher and one subscriber can tell it was added to be seen. Saying which service was
removed and why is worth more than the service would have been.

---

## 5. The watcher can read the archive, and still cannot rewrite it

**Decided:** 19 August 2026, when the watcher first needed yesterday's page.

Comparing today with yesterday needs yesterday, so the watcher needs to read the snapshot archive.
It held `storage.objectAdmin`, which would have done it, and which also allows overwrite and delete.

That would have quietly ended the strongest claim in the build. Decision 1 says the archive earns its
place because the process that fills it cannot revise it. An archive the watcher can rewrite is an
archive whose history is only as good as the watcher, and the watcher is the one component whose
entire job is to make claims about the past.

**So the watcher now holds `storage.objectViewer` plus `storage.objectCreator`, and no longer holds
`objectAdmin`.** It can add a snapshot and read one back. It cannot overwrite one and it cannot
delete one. The researcher stays creator only and still cannot read.

This is a claim, so it gets a test rather than a sentence, in `tools/test_isolation.py`.

---

## 6. The international share ranks institutions and is never shown

**Decided:** 19 August 2026.

The share comes from Times Higher Education, which is a publisher rather than a government and a
commercial one. It is used as an ordering key when deciding which institutions to put in front of
somebody, and it is not displayed and not cited to a user.

**What that changes.** A number we show is a claim we make, and a claim needs a source the reader can
check. A number that only decides what order a list comes in is not a claim to the reader at all, so
the question it has to answer is narrower: is the ordering better with it than without.

**What it does not change.** The provenance is still stored on every row: publisher, edition, the
verbatim span the figure was read from, the source URL and the date read. Not displaying something is
not a reason to stop recording where it came from, and the day anybody asks why one school appeared
above another, the answer exists.

**What is still true and still the user's to weigh.** These are somebody else's figures. Using them
internally is a lighter question than republishing them, and it is not no question.

**The coverage this ranks over.** 97 of 946 UK institutions have a published share. The register is
mostly language schools, private colleges and independent schools, which no ranking covers. So the
share orders universities and says nothing about the rest, and anything built on it has to behave
sensibly when the key is absent rather than treating unranked as worst.

---

## 7. The agent chooses what to read. It does not get to choose what is true

**Decided:** 19 August 2026.

A Google agent framework is mandatory for this event, which is exactly the condition under which a
framework gets bolted on, does nothing, and is described in the submission as though it did. So the
question was not whether to use ADK. It was which part of the work is genuinely a judgment, because
that is the only part worth handing to an agent.

**The judgment is which pages to open.** Until now a lane was read by walking every link a government
publishes to depth one and running the same prompt over everything that came back. That works and it
is indiscriminate: pages that matter and pages that do not arrive from the same index and get the
same attention. Deciding that a page about fee schedules for people already resident is not worth a
read, and that the eligibility page linked next to it is, is not something a rule expresses well.

**Everything else stays in code, and the difference is enforced rather than requested.** The agent
holds no ability to fetch, so it cannot fetch a page robots.txt disallows. It holds no ability to
write a requirement, only to offer one to a tool that checks the quote against the page that was
actually fetched in that session and refuses it otherwise. The citation is assembled from the fetch,
as it already was. A rule an agent can decide to skip is not a rule, so none of these are in the
prompt as instructions.

**The refusals are counted and returned.** A session reports what it was refused and why, alongside
what it kept. An agent that had nine of ten quotes rejected has told us something about the run, and
swallowing that would hide it.

**ADK's own model client is not used.** ADK ships a client that would open its own connection to
Vertex with its own idea of what to do about a 429. Everything else in this product goes through
`migragent/model.py` because of D20, where five callers each retrying differently turned one rate
limit into three unrelated looking bugs. The agent is the chattiest caller in the system, so letting
it out of that rule would have left the rule true of everything except the thing it matters most for.
`migragent/agent_llm.py` is a `BaseLlm` that ADK drives and that calls the same retry loop.

**That claim is checked rather than asserted.** `tools/test_agent.py` replaces ADK's client with one
that raises if anything constructs it, runs a full session against a scripted model and a fake
fetcher, and reports 11 checks: the model calls arrived through our caller, the tools survived the
trip to the wire, a quote that is not on the page was refused, a real quote attributed to a page the
agent never opened was refused, the disallowed page was never fetched, and the citation came from
the fetch.

**The cost accepted.** `google-adk` brings FastAPI, Uvicorn, OpenTelemetry and google-genai, and one
`requirements.txt` builds both the web service and the ingestion job, so the web image now carries
dependencies it does not use. Splitting them means a second Dockerfile and a second dependency set
to keep in step, which is a standing cost to avoid a one time one. One image, and the reason is
written here rather than left for somebody to wonder about.

---

## 8. The CV is scored against a job, not against a country

**Decided:** 20 August 2026.

Every other document a person uploads answers a question a government asked. A CV answers nobody's
question, so it needed its own rules, and there were three choices to make.

**It stays out of the readiness score.** Readiness is the share of a government's extracted
requirements that a person's documents cover. A CV covers almost none of them. Letting it move that
number would have made the one honest number in the product dishonest, in exchange for a bar that
goes up when somebody uploads a file.

**Its number is fit against one listing.** Not a grade for the document, not a guess at a country's
taste in CVs. Fit is the share of what a posting says it wants that the CV can be shown to evidence,
and every line of it shows the posting's own sentence next to the person's own. That makes the
number arguable, which is the point: a person can look at a row and disagree with it.

**It says fit and never says you will get the job.** That sentence is stored on the score itself
rather than written into a template, so nothing can show one without the other.

**What is enforced in code rather than asked for in the prompt.** The requirement must carry a
verbatim quote that is really on the posting. The evidence must be a claim the CV actually made,
checked by membership against claims already read and quote-checked out of the document. A model
cannot credit somebody with a certificate because the job asks for one.

**What that cost, and the correction.** The first version also forbade paraphrase, and the model
read that as permission to refuse anything not worded identically: a welder with seven years of
drawings work scored 0% against a job asking him to read drawings. Judgment and citation are two
different things, and they are now two different instructions. Judge the substance, copy the claim
exactly. Same CV, same postings: 17% and 38%, with the matched rows showing which line did it.

**Rewrites are drafts, and their numbers are checked.** A model asked to make a CV fit a job will
round three years up to five. So a rewrite may only use claims already read from the CV, and every
number in the finished draft is checked against the numbers in those claims, with anything else
listed on the draft in front of the person. Layout advice is labelled convention, because no
government publishes a required CV format and the guide's authority comes from citing one that does.

---

## 9. The people finder searches, and says so

**Decided:** 20 August 2026, by the user, against my recommendation. Recorded that way because a
decision somebody overrode is the one most worth being able to find later.

The "people worth speaking to" feature came from `dossier`, which used a search API. I proposed
reading only an employer's own public pages, so the robots gate would govern this feature like
everything else. The call was Vertex's Google Search grounding instead: better coverage, and a
Google tool, which suits the event.

**What that costs, stated plainly rather than glossed.** Search grounding does not crawl. It reads an
index of pages somebody else fetched, so our robots gate does not apply to it and cannot. The
submission previously said this product does not touch what it is not allowed to crawl. That sentence
is now false as written and becomes: **everything this pipeline fetches goes through the gate, and
the people finder does not fetch, it asks Google.** People found this way are labelled as found
through Google Search wherever they appear.

**Three things are enforced in code, because the first real run needed all of them.**

Asked about Nomad Hauling Inc, a hauling firm in Merritt, British Columbia, grounding fired
thirty-seven searches and answered confidently about Nomad Inc, an AI fleet platform in Toronto. The
Chicago Booth failure again: true, and about the wrong subject.

- **The company is checked before anybody is kept.** The model must name what it found, and it is
  matched against the employer on the listing. A single significant word must match exactly, because
  a subset rule alone lets "Nomad Inc" pass as "Nomad Hauling Inc", which is the exact case.
- **The place is checked too.** Two real companies share a name far more often than they share a name
  and a town.
- **The source must be one the search returned.** This needs two calls and the reason is measured: a
  grounded call answering in prose comes back with real `groundingChunks`, and the same call asked
  for JSON comes back with the queries and no sources at all, while still naming plausible websites
  from memory. Naming a real person at a real company against a source the model invented is not
  worth shipping. So: search in prose with its sources, then structure the notes with no search, and
  drop anybody whose source is not on the list.

**No contact details, ever.** No email, no phone, no address. Stripped in code rather than asked for
in the prompt. This is "here is who does this job", not a lead list.

**What it actually returns.** Regency Fireplace Products: four people, correct roles, every one with
a live source link. Nomad Hauling: one, the owner, from a legal notices publication. That second
result is the edge worth watching. He is the right person to contact about a job at his own company,
and he is also a private individual at a micro business who was published for an unrelated reason.
The feature is working as designed and the design has a boundary near there.

---

## 10. The agent reads where the walk is thin, and does not replace it

**Decided:** 23 August 2026, after running `tools/compare_agent.py` on two lanes rather than
switching the pipeline over on the strength of one good gov.uk page. Nothing was written by either
run.

Build 4 ended with the agent built, proven in a test, and switched off, because nobody had compared
a whole lane it read against the same lane the walk read. That comparison has now run twice, once
where the walk is deep and once where it is thin, and the two answers point in opposite directions.
Which is the finding.

**UK work, where the walk holds 174 live requirements from 19 pages.** The agent read 3 pages, took
32 turns, refused nothing, and stopped by its own choice with 5 pages of its budget unspent. It
returned 26 requirements. Sixteen sentences were found by both. The walk kept 139 the agent never
saw. On volume this is not close.

But the 10 it found alone are not filler. The application fee of 819 pounds and the 628 pound fee
for a job on the immigration salary list, the criminal record certificate for applications from
outside the UK, the PhD salary discount and what it requires, and each family member applying
separately. It got them by opening `/skilled-worker-visa/print`, which is the whole guide on one
page, and reading it as a document. The walk had that page in the registry and treated it as one
more page among twenty.

**Germany study, where the walk holds 26 requirements from 4 pages.** The agent read 7 pages and
returned 29, with a higher share carrying a number, and 4 of its 7 pages were not in the registry at
all: arrival registration, EU student mobility, and the notification deadline that goes with it.
Eleven sentences shared, 18 only the agent, 14 only the walk. Here it is better on nearly every axis
and it widened the registry while doing it.

**Why the two disagree, and it is not the model.** The walk finds pages by structure and reads
whatever it finds. Where a government publishes a lot and links it plainly, that is a strength and
the agent cannot match it in one session with a page budget. Where a government publishes across
sections that do not link to each other, structure runs out and choosing what to open next is worth
more than reading more.

**So the daily round is not handed to the agent.** `MIGRAGENT_RESEARCHER` stays unset for lanes the
walk covers deeply. The agent runs as a second pass on thin lanes, where thin is measured from the
corpus rather than guessed, and the pages it opens get registry rows so the watcher keeps them.

**One thing it did that the walk cannot, and it is the D29 failure it walks past.** On the German
lane the agent opened a page under the site's Arbeit section, read it, and recorded nothing from it.
The walk gives a discovered page the lane of the entry that found it, which is how Skilled Worker
rules ended up in a study guide (D32). An agent reading for a stated question can look at a page and
decide it is about a different question. That is not a fix for per page lane detection, which is
still open, and it is the first thing in this build that has ever declined a page on subject.

---

## The watch: three signals, no fourth

The product's second promise is that it tells you when something changes. Deciding *what* counts as
something is the whole design, and the answer is: only what the pipeline already observes.

- **A rule moved.** A change row the daily round wrote, where the explainer said the difference is
  material. Immaterial changes never reach a person. D23 is the reason that flag exists: on the
  first real watch round, 95 of 143 pages reported a different digest and not one added or removed
  line of text. A watcher that cries wolf daily teaches somebody to ignore the day it matters.
- **A door opened.** An occupation added to a country's shortage list, or a school added to the
  register that licenses it to take international students. Both were invisible before this build,
  because `merge=True` writes make a row added today and a row added in June look identical. So
  both stores now ask which ids are new before writing them (`migragent/newness.py`), and stamp
  `first_seen_at` once. A register loaded before this build has no new rows and produces no alerts,
  which is correct: we do not know when those schools were added, so we do not say.
- **A job you qualify for.** A posting first seen since the mark, in an occupation the person's own
  CV matched. The occupations are recomputed at digest time rather than stored on the watch, so a
  better CV changes what you are told about.

**There is no fourth signal, and in particular there is no deadline countdown.** "Your application
closes in 6 days" would need a date we can only sometimes source and would be the one line on the
screen most likely to be wrong about somebody's future.

**Nothing is generated at the moment of telling somebody.** The digest makes no model calls and
fetches nothing; every sentence in an alert was written by the round, by a government, or by
`migragent/alerts.py`. That is what lets an alert carry the same evidence a requirement carries.

**Ids are derived from the case and the thing that happened**, so a digest that runs twice writes
the same documents rather than a second copy, and `seen_at` is kept off the merge payload so a
re-run cannot mark something unread that somebody has already read. The mark moves only after the
alerts are written: a crash between the two repeats harmlessly, and a mark moved first would mean a
change nobody is ever told about.

**Delivery is in-app and says so.** There is no mail sender in this project. `Alerts.pending()`
hands out exactly what an email or a push would need and nothing consumes it yet. A notification
channel that half exists is worse than one that does not, because people plan around it.

