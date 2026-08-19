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
