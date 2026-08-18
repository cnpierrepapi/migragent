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
