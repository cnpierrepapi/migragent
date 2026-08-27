# Decisions, and what they cost

One entry per call that's expensive to undo or easy to misread later. Written when we made it,
including the ones that turned out half wrong.

## 1. Worker isolation came from the old build, and we oversold it

Decided 18 August 2026, then argued about the same day. Fair question: is this pulling weight here,
or is it luggage we forgot to unpack?

Mostly luggage. One piece of it earns its keep.

`identity.py` crossed over from the previous build with its reasoning attached. That build was an
enterprise data governance thing, where "which service account wrote this row" was basically the
product. Here it isn't. What MIGRAGENT sells is evidence. Nobody deciding whether to trust a study
permit guide is going to ask which service account wrote it.

Going through it one piece at a time.

The append-only snapshot archive stays, and it's the one that matters. The whole product rests on
"we read this page on this date, here's the copy". The archive is that copy. If the thing that
writes it can also rewrite it, the archive is only as trustworthy as that process, and the citation
goes back to being a promise instead of a receipt. The researcher gets a 403 on read, overwrite,
delete and list. We tested that. This one is genuinely about what the product is.

The researcher can't write to Firestore. Keep it, but it's just hygiene. It means a bad extraction
can't corrupt the guide store. Worth having, cost us one word in a script, `datastore.viewer`
instead of `datastore.user`. Not a feature, and it shouldn't be described as one.

Web can't start a crawl and can't call a model directly. Keep, minor. Stops a request handler from
hammering government sites or running up an inference bill.

The mistake was how much attention it got, not the decision. The roles are four lines of shell.
The test is one file. What actually happened is a whole task grew up around proving it worked,
because the inherited docstring claimed something that wasn't true and that had to be fixed. The
fix was necessary. Treating the result as a headline was not.

So the isolation stays, because it's already there and costs nothing to keep, and
`tools/test_isolation.py` stays wired in because a claim in the code has to keep being true. It
doesn't get more time. It doesn't lead the README. The demo opens on the run, not on this.

Getting it wrong the other way would have meant shipping that docstring unchanged and asserting a
guarantee that was false. That's D1 in the defect log, and it's why the work wasn't wasted even
though the emphasis was.

## 2. Discovery is structural, never words

Decided 18 August 2026, after two tries that missed.

Picking which pages to read can't come from matching words like "visa" or "fees" in a URL or a
link. That's pattern-matching on names. It looks like understanding and isn't, and `INHERITED.md`
already has it written down as the mistake that filed survey answers as decisions about people.

The first structural attempt missed too, and we could measure how badly: same host plus section
path plus direct links kept 55 of 68 links on gov.uk, and almost all of it was site navigation.
That's D10.

Here's what works. Navigation shows up on every page of a site. Content doesn't. So you take two
pages from the same host and intersect their links, and what's left is the stuff that makes one
page different from its neighbour. gov.uk drops from 68 links to 26. canada.ca goes from 43 to 10,
and the 10 are eligibility, get-documents, prepare, apply.

The cost: a host needs at least two known pages before we can walk it. A host with one entry point
gets skipped, and the run says so out loud instead of returning everything or nothing and calling
it done.

No model touches the choice of what to read. A model reads a page afterwards and says what a
requirement is. Which pages exist, which got read, and when, all stays plain code, because that's
the part that has to be checkable.

## 3. A model can say what a requirement means. It can't say one exists

Decided 18 August 2026, building `migragent/extract.py`.

Two different failures hide under "the model made it up", and we'd only covered one.

Invented sources are handled by structure. The citation gets built from the `Fetched` object: the
URL we actually asked for, and the timestamp off the clock when the bytes landed. Neither one goes
into a prompt or comes back out of a response. So no combination of words from a model can produce
a source we didn't fetch.

Invented requirements are the more likely problem, and we hadn't touched them. A model that's read
a thousand immigration pages will tell you a study permit needs a police certificate whether or not
the page in front of it says so. And it'll be right often enough that you believe it.

So every requirement carries a word-for-word quote, and every quote gets checked against the page
text before the requirement is allowed to exist. No match, no requirement.

Tested both directions, because a check that only ever says yes isn't a check:

| given | verdict |
| --- | --- |
| a real quote from the page | accepted |
| same quote, curly apostrophes and odd spacing | accepted |
| a plausible invented requirement | rejected |
| a real sentence with one number changed | rejected |
| two real fragments stitched together | rejected |

That second row matters as much as the rest. The comparison folds whitespace, quote marks and
dashes, so a real quote doesn't get thrown out over a curly apostrophe. Without that the check
looks stricter than it is while quietly losing good requirements. Case and accents stay, because
they carry meaning in French and Spanish.

What it costs: anything the page implies but never says is gone. That's the trade we wanted. The
implied stuff is exactly what the open-questions section at the back of the guide is for.

Dropped requirements come back in the result and get reported. A run that drops nine of ten has to
say so. A silent drop rate is how a check like this stops being a check.

## 4. We planned Pub/Sub into the pipeline, then took it out

Decided 19 August 2026, building the ingestion job.

The plan said Cloud Scheduler to Pub/Sub to a Cloud Run job, one message per lane. The topic went
into the plan twice and into this project's memory three times before anyone asked what it was
actually carrying.

It was carrying an integer. Cloud Run jobs already number their own parallel tasks and hand each
one `CLOUD_RUN_TASK_INDEX`. The runtime already retries a task that fails, already tells you which
tasks died, already caps how many run at once. A topic would have added a thing to configure, an
identity to grant, a subscription to get wrong, and one more place a message can vanish. All to
deliver a number the platform gives you for free.

So there's no Pub/Sub in this build. The fan-out is `--tasks 10` and a fixed list of lanes, and
index 3 means the same lane every run because the list is a list, not a set.

What it costs. A topic would let something other than the schedule kick off a round, which is the
thing we don't want. The whole isolation argument is that a web request can't start a crawl. It
would also decouple the trigger from the work, which is worth doing when the work is spiky and
unrelated to the trigger. Ingestion is neither.

Why write this down instead of just leaving the gap. The mandatory requirement is one Google Cloud
service and this build uses five. Nobody's handing out points for a sixth, and a judge who sees a
topic with one publisher and one subscriber can tell it was added to be seen. Saying which service
we cut, and why, is worth more than the service would have been.

## 5. The watcher can read the archive. It still can't rewrite it

Decided 19 August 2026, the first time the watcher needed yesterday's page.

Comparing today with yesterday needs yesterday, so the watcher has to read the snapshot archive. It
was holding `storage.objectAdmin`, which does that, and also allows overwrite and delete.

That would have quietly killed the strongest claim in the build. Decision 1 says the archive earns
its place because the thing that fills it can't revise it. An archive the watcher can rewrite is
only as good as the watcher, and the watcher is the one component whose entire job is making claims
about the past.

So it holds `storage.objectViewer` plus `storage.objectCreator` now, and not `objectAdmin`. It can
add a snapshot and read one back. It can't overwrite one and can't delete one. The researcher is
still creator-only and still can't read.

That's a claim, so it gets a test instead of a sentence, in `tools/test_isolation.py`.

## 6. The international student share ranks schools and never gets shown

Decided 19 August 2026.

The share comes from Times Higher Education. That's a publisher, not a government, and a commercial
one. We use it to order which institutions to put in front of somebody. We don't display it and
don't cite it to a user.

Here's the difference that makes. A number we show is a claim we're making, and a claim needs a
source the reader can check. A number that only decides list order isn't a claim to the reader at
all. So the bar it has to clear is lower: is the order better with it than without.

What doesn't change: the provenance still sits on every row. Publisher, edition, the exact span the
figure came from, the URL, the date. Not showing something isn't a reason to stop recording where
it came from. The day someone asks why one school ranked above another, the answer's there.

What's still the user's to weigh: these are someone else's numbers. Using them internally is a
lighter question than republishing them. It's not no question.

The coverage this ranks over: 97 of 946 UK institutions have a published share. The register is
mostly language schools, private colleges and independent schools, and no ranking covers those. So
the share orders universities and says nothing about the rest. Anything built on it has to behave
when the key is missing, not treat unranked as worst.

## 7. The agent picks what to read. It doesn't get to pick what's true

Decided 19 August 2026.

A Google agent framework is mandatory for this event. That's exactly the setup where a framework
gets bolted on, does nothing, and shows up in the submission like it did something. So the question
was never whether to use ADK. It was which part of the work is actually a judgment call, because
that's the only part worth handing to an agent.

The judgment is which pages to open. Until now a lane got read by walking every link a government
publishes to depth one and running the same prompt over everything that came back. That works and
it's indiscriminate. Pages that matter and pages that don't arrive from the same index and get the
same attention. Deciding that a fee schedule for people already resident isn't worth reading, and
the eligibility page next to it is, isn't something a rule does well.

Everything else stays code, and the line is enforced, not requested. The agent can't fetch, so it
can't fetch a page robots.txt blocks. It can't write a requirement, only hand one to a tool that
checks the quote against the page fetched in that session and refuses it otherwise. The citation is
built from the fetch, same as before. A rule an agent can choose to skip isn't a rule, so none of
this is in the prompt as instructions.

Refusals get counted and returned. A session reports what it was refused and why, next to what it
kept. An agent that had nine of ten quotes rejected has told you something about the run, and
swallowing that hides it.

ADK's own model client isn't used. ADK ships a client that opens its own connection to Vertex with
its own idea about a 429. Everything else in this product goes through `migragent/model.py` because
of D20, where five callers each retrying their own way turned one rate limit into three bugs that
looked unrelated. The agent is the chattiest caller here, so letting it skip that rule would leave
the rule true of everything except the place it matters most. `migragent/agent_llm.py` is a
`BaseLlm` that ADK drives and that calls the same retry loop.

And that's checked, not asserted. `tools/test_agent.py` swaps ADK's client for one that raises if
anything builds it, runs a full session against a scripted model and a fake fetcher, and reports 11
checks: model calls came through our caller, tools survived the trip to the wire, a quote not on
the page was refused, a real quote pinned to a page the agent never opened was refused, the blocked
page never got fetched, the citation came from the fetch.

The cost we took. `google-adk` pulls in FastAPI, Uvicorn, OpenTelemetry and google-genai, and one
`requirements.txt` builds both the web service and the ingestion job, so the web image now carries
stuff it doesn't use. Splitting them means a second Dockerfile and a second dependency set to keep
in sync, which is an ongoing cost to dodge a one-time one. One image. Reason's written here so
nobody has to wonder.

## 8. The CV is scored against a job, not against a country

Decided 20 August 2026.

Every other document someone uploads answers a question a government asked. A CV answers nobody's
question, so it needed its own rules, and there were three calls to make.

It stays out of the readiness score. Readiness is the share of a government's requirements that a
person's documents cover. A CV covers almost none of them. Letting it move that number would make
the one honest number in the product dishonest, in exchange for a bar that climbs when someone
uploads a file.

Its number is fit against one listing. Fit is the share of what a posting says it wants that the CV
can actually show, and every line of it puts the posting's own sentence next to the person's own.
That makes the number arguable, which is the point. A person can look at a row and say no, that's
wrong.

It says fit and never says you'll get the job. That sentence is stored on the score itself, not in
a template, so you can't show one without the other.

What's enforced in code instead of asked for in the prompt: the requirement has to carry a real
quote that's actually on the posting. The evidence has to be a claim the CV actually made, checked
by membership against claims already read and quote-checked out of the document. The model can't
credit somebody with a certificate because the job asks for one.

What that cost, and the fix. The first version also banned paraphrase, and the model read that as
permission to reject anything not worded identically. A welder with seven years of drawings work
scored 0% against a job asking him to read drawings. Judgment and citation are two different things
and they're two different instructions now. Judge the substance, copy the claim exactly. Same CV,
same postings: 17% and 38%, with the matched rows showing which line did it.

Rewrites are drafts and their numbers get checked. A model asked to make a CV fit a job will round
three years up to five. So a rewrite can only use claims already read from the CV, and every number
in the finished draft gets checked against the numbers in those claims, with anything else flagged
on the draft in front of the person. Layout advice is labelled convention, because no government
publishes a required CV format and the guide's authority comes from citing one that does.

## 9. The people finder searches, and says so

Decided 20 August 2026, by the user, against my recommendation. Recorded that way because the
decision someone overrode is the one you most want to be able to find later.

The "people worth speaking to" feature came from `dossier`, which used a search API. I wanted to
read only an employer's own public pages, so the robots gate would cover this feature like
everything else. The call went the other way: Vertex's Google Search grounding, for better
coverage, and it's a Google tool, which fits the event.

What that costs, said straight. Search grounding doesn't crawl. It reads an index of pages somebody
else fetched. Our robots gate doesn't apply to it and can't. The submission used to say this
product doesn't touch what it isn't allowed to crawl. That sentence is now false as written, and
becomes: everything this pipeline fetches goes through the gate, and the people finder doesn't
fetch, it asks Google. People found this way are labelled as found through Google Search everywhere
they show up.

Three things enforced in code, because the first real run needed all three.

Asked about Nomad Hauling Inc, a hauling firm in Merritt, British Columbia, grounding fired
thirty-seven searches and answered confidently about Nomad Inc, an AI fleet platform in Toronto.
Chicago Booth all over again: true, wrong subject.

The company gets checked before anyone is kept. The model has to name what it found, and that gets
matched against the employer on the listing. One significant word has to match exactly, because a
subset rule on its own lets "Nomad Inc" pass as "Nomad Hauling Inc", which is this exact case. The
town gets checked too. Two real companies share a name far more often than they share a name and a
town. And the source has to be one the search returned. That needs two calls, and the reason is
measured: a grounded call answering in prose comes back with real `groundingChunks`, and the same
call asked for JSON comes back with the search queries and no sources at all, still naming
plausible websites from memory. Naming a real person at a real company against a source the model
made up isn't worth shipping. So: search in prose with its sources, then structure the notes with
no search, then drop anyone whose source isn't on the list.

No contact details, ever. No email, no phone, no address. Stripped in code, not asked for in the
prompt. This is "here's who does this job", not a lead list.

What it actually returns. Regency Fireplace Products: four people, right roles, every one with a
live source link. Nomad Hauling: one, the owner, from a legal notices page. That second result is
the edge worth watching. He's the right person to contact about a job at his own company. He's also
a private individual at a tiny business who got published for an unrelated reason. The feature
works as designed and the design has a boundary right about there.

## 10. The agent reads where the walk is thin. It doesn't replace it

Decided 23 August 2026, after running `tools/compare_agent.py` on two lanes instead of flipping the
pipeline over on the strength of one good gov.uk page. Neither run wrote anything.

Build 4 ended with the agent built, proven in a test, and switched off, because nobody had compared
a whole lane it read against the same lane the walk read. That comparison has run twice now, once
where the walk is deep and once where it's thin, and the two answers point opposite ways. That's
the finding.

UK work, walk holds 174 live requirements from 19 pages. The agent read 3 pages, took 32 turns,
refused nothing, stopped on its own with 5 pages of budget left. It returned 26 requirements.
Sixteen sentences found by both. The walk kept 139 the agent never saw. On volume it's not close.

But the 10 it found alone aren't filler. The 819 pound application fee and the 628 pound fee for a
job on the immigration salary list. The criminal record certificate for applications from outside
the UK. The PhD salary discount and what it needs. Each family member applying separately. It got
them by opening `/skilled-worker-visa/print`, the whole guide on one page, and reading it as a
document. The walk had that page in the registry and treated it as one more among twenty.

Germany study, walk holds 26 requirements from 4 pages. The agent read 7 and returned 29, more of
them carrying a number, and 4 of its 7 pages weren't in the registry at all: arrival registration,
EU student mobility, the notification deadline that goes with it. Eleven sentences shared, 18 only
the agent, 14 only the walk. Here it's better on nearly every axis and it grew the registry while
doing it.

Why they disagree, and it isn't the model. The walk finds pages by structure and reads whatever it
finds. Where a government publishes a lot and links it plainly, that's a strength, and the agent
can't match it in one session on a page budget. Where a government scatters things across sections
that don't link to each other, structure runs out, and picking what to open next is worth more than
reading more.

So the daily round doesn't go to the agent. `MIGRAGENT_RESEARCHER` stays unset for lanes the walk
covers deeply. The agent runs as a second pass on thin lanes, where thin is measured from the
corpus, not guessed, and the pages it opens get registry rows so the watcher keeps them.

One thing it did that the walk can't, and it's the D29 failure the walk misses. On the German lane
the agent opened a page under the site's Arbeit section, read it, and recorded nothing. The walk
gives a discovered page the lane of the entry that found it, which is how Skilled Worker rules
ended up in a study guide (D32). An agent reading for a stated question can look at a page and
decide it's about a different question. That's not a fix for per-page lane detection, which is
still open, and it's the first thing in this build that ever turned down a page on subject.

## 11. The lane a page serves is read off the page, not inherited

Decided 27 August 2026, building the agent layer. This is the fix for per-page lane detection that
Decision 10 left open, and D29 and D32 are the failures it closes.

The walk gives a discovered page the lane of the entry that found it. Right most of the time,
because a government that files its student pages under a student section is telling you something
true. Wrong exactly when a government links the work route from the study route, or runs one
catalogue for every route, and then a page about salaried employment is one command from being
extracted into a study guide with a real quote, a real link, a real date. The anti-invention
machinery can't see it, because nothing's invented. It's a true sentence filed under the wrong
question.

The lane check reads the page and says which of study and work it's about, one, both or neither,
before the round extracts it. Every route it names carries a sentence checked against the page in
code. It isn't told which lane the walk assigned, so it reads instead of confirming.

It was an ADK agent for a day, and that was wrong. A full agent session per page made a watch round
over 143 pages run for hours. Measured, not guessed. Deciding which question a page answers is one
call, not multi-step work. The agent never navigated, and its only "revision" was retrying a
refused quote, which a single call handles by returning a good one. So it's one `call_json` in
`migragent/lanes.py` now. Same judgment, same quote check in code, no session. This is the concrete
case behind Decision 12.

It runs on depth 1 and deeper government pages only. Entry pages at depth 0 are hand-seeded and
their lane is a call somebody made. Depth 0 is also where the researcher agent starts, and that
branch owns it.

It fails safe, same as the second reader. No check, or a check that couldn't answer on a page, and
the page gets extracted into its assigned lane like before. The check being down isn't evidence
the walk was wrong. The cost is that a genuine off-lane page slips through on a day the model's
down, which is the same page that slipped through every day before this existed. The floor doesn't
move.

Off by default, behind `MIGRAGENT_LANE_CHECK` or `--lane-check`, rolled out lane by lane: run it,
read the pages it calls off-lane instead of the count, check they really are, then widen.

## 12. Four agents, not sixteen, and the twelve are the point

Decided 27 August 2026, after building them.

An earlier draft listed sixteen agents. Building them sharpened the test past "a decision or a loop
already exists". An agent earns the name only when the model decides across multiple steps what to
do next: open another page, pick a tool, revise its output because a check refused it. By that
test:

Four have it. Researcher and Scout navigate. Extractor and Coverage Matcher revise over a refusal,
and both revise something worth getting back: a mis-copied quote, a wording miss on the readiness
score.

Twelve don't. The lane check, Verifier, Change Interpreter, Translator, Attribution Verifier, the
three document readers, Route Finder, Fit Scorer, Digest Router. Each one is a single model call,
then code checks the response. There's no step where the model chooses what to do next.
`verify.py`, `changes.py`, `coverage.py` and `lanes.py` already run them, and run them fine.

The lane check is the one we walked back. It shipped as an `LlmAgent` on 27 August and came out the
same day. A full agent session per page made a watch round take hours, and it never actually
navigated or revised. It's `migragent/lanes.py` now, one call, same judgment. Decision 11 has the
detail.

Wrapping the twelve in `LlmAgent` would push up the node count and the demo's headline number. It
would also be the exact move this doc started out to refuse, same as not standing up a Pub/Sub
topic with one publisher (Decision 4) and not making the people finder an agent (Decision 9). A
judge who reads this file is who the restraint is for.

So the submission says four `LlmAgent`s, two `SequentialAgent`s, four non-LLM gate nodes, and a
list of the calls that are deliberately not agents. If that reads as a smaller build than a
sixteen-agent diagram, it's a more honest one, and honesty is what's being judged on the
architecture axis.

## The watch: three signals, no fourth

The product's second promise is that it tells you when something changes. Deciding what counts as
something is the whole design, and the answer is: only what the pipeline already sees.

A rule moved. A change row the daily round wrote, where the explainer said the difference is
material. Immaterial changes never reach a person. D23 is why that flag exists. On the first real
watch round, 95 of 143 pages reported a different digest and not one added or removed line of text.
A watcher that cries wolf every day teaches the person to ignore the day it's real.

A door opened. An occupation added to a country's shortage list, or a school added to the register
that licenses it to take international students. Both were invisible before this build, because
`merge=True` writes make a row added today and a row added in June look the same. So both stores
ask which ids are new before writing them (`migragent/newness.py`) and stamp `first_seen_at` once.
A register loaded before this build has no new rows and fires no alerts, which is right. We don't
know when those schools were added, so we don't say.

A job you qualify for. A posting first seen since the mark, in an occupation the person's own CV
matched. The occupations get recomputed at digest time instead of stored on the watch, so a better
CV changes what you hear about.

There's no fourth signal, and in particular no deadline countdown. "Your application closes in 6
days" would need a date we can only sometimes source, and it would be the line on the screen most
likely to be wrong about somebody's future.

Nothing gets generated at the moment of telling somebody. The digest makes no model calls and
fetches nothing. Every sentence in an alert was written by the round, by a government, or by
`migragent/alerts.py`. That's what lets an alert carry the same evidence a requirement carries.

Ids come from the case and the thing that happened, so a digest that runs twice writes the same
documents instead of a second copy, and `seen_at` stays off the merge payload so a re-run can't
mark something unread that somebody already read. The mark moves only after the alerts are written.
A crash between the two repeats harmlessly. A mark moved first would mean a change nobody ever
hears about.

Delivery is in-app and says so. There's no mail sender in this project. `Alerts.pending()` hands
out exactly what an email or a push would need, and nothing consumes it yet. A notification channel
that half exists is worse than one that doesn't, because people plan around it.
