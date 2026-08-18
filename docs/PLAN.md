# The plan

Four builds. Each one ends with something that works on a live URL, not with a half-finished layer.
Deadline is 31 August, 5pm PDT, so finishing the four builds around the 22nd leaves real buffer for
the video and for the things that always go wrong.

**Where it lives:** Cloud Run, service named `migragent`, so the URL carries the name. The backend
has to be on Google Cloud because the video must show it running there, and the app holds user
documents and a service account, so it stays inside the same project rather than exporting a key to
another provider.

---

## Build 1 — The working guide

**Ends with:** fill in the form on a live URL, and get back a PDF with real requirements and real
citations.

This is the checkpoint. Everything after it makes the guide better; nothing after it is needed for
the guide to exist.

- Cloud Run service, deploy path, one page that serves
- The intake form. Three lanes offered, **Canada study permit built deep first** because there is a
  real blocked case behind it
- **The source reader.** Fetch the official page, extract the requirements with Gemini, attach the
  link and the date read. The citation comes from the fetch, never from the model, so it cannot be
  invented
- ADK on the researcher, and only there: deciding a source needs a sibling page, fetching it, and
  stopping when the requirement is complete is real multi-step work. The fetching, hashing and
  rendering around it stays plain code on purpose
- The guide: ordered steps, dependencies, cost, duration, sources on every line, open questions at
  the back for anything that could not be sourced
- Rendered as a document and downloadable as PDF

## Build 2 — Documents and gaps

**Ends with:** uploading a transcript changes what the guide says you still need.

- Upload passport, transcript, degree, English test, registration
- Gemini reads them. This is the multimodal work, and it is also what the Best Multimodal UX
  category is for
- Match uploads against requirements: what is satisfied, what is missing, what is expiring
- **Routes for every gap.** No English test yet means the accepted tests, their cost and their
  booking lead time. A second class lower degree means the programmes and bridging routes that
  accept one, and the ones that do not. A missing route is still an answer
- Second lane built deep: nursing registration in Canada
- **Data protection from the start, not retrofitted:** a stated retention window, encryption, and a
  delete-my-data path that works. People are uploading passports

## Build 3 — The watcher

**Ends with:** a daily round runs by itself, catches a real change, and the change line shows it.

- **The source registry is data, not code.** Adding site 101 is a row in Firestore, not a deploy.
  That is what makes a count of sources a real claim
- Cloud Scheduler fires daily, Pub/Sub fans out, Cloud Run jobs fetch
- Raw snapshots to Cloud Storage, because "the date it was read" needs the page behind it and
  because tomorrow has to diff against today
- **Hash first.** If the page is byte-identical, stop. No model call, no cost. Most government pages
  do not change most days, so the daily bill is fetches, not inference
- On a change: diff, Gemini explains what moved, both versions and both dates recorded with the
  source
- **The change line**, seeded from published government change history with their dates. Real
  changes only. No agent run is ever backdated
- **The country watch screen.** Where policy has loosened and where it has tightened, from the
  observed record. This is the part nobody else is building and it is the reason someone renews
- Politeness: robots.txt respected, the crawler identifies itself, backs off, and caches

## Build 4 — Accounts, notifications, submission

**Ends with:** sign in, get told when your guide moves, and the entry is submitted.

- Firebase Auth for accounts
- Persistent memory per user in Firestore: their case, their documents, their guide, their
  watchlist, and what they have already been told so they are not told twice
- Routing a change to the people it affects, using embeddings and vector search rather than running
  every source against every user
- Browser notification permission, asked for properly, fired when a guide changes
- Architecture diagram, README a stranger can follow, the four minute video

---

## What gets cut if it tightens, decided now rather than on the 30th

**Lane depth, never rigour.** Two lanes done properly beats three done shallowly. The third lane
stays in the form and says plainly that it is not covered yet.

**The country watch screen ships read-only before it ships personalised.**

**What does not get cut:** nothing is stated without a source, no run is ever backdated, and the
source count shown is the real one. If 40 sources are verified on submission day, it says 40.

---

## The three mandatory requirements, and where each one lives

| Required | Where |
| --- | --- |
| Gemini 3.5 or newer | Extracting requirements, reading uploaded documents, explaining a diff |
| A Google agent framework | ADK, on the researcher only |
| A Google Cloud infrastructure service | Cloud Run, Firestore, Pub/Sub, Cloud Scheduler, Cloud Storage |

There are no marks for touching more Google products. The rubric is Innovation and Utility 40%,
Architectural Discipline 30%, Demo and Readiness 30%. Every service above earns its place or it does
not go in, and the restraint gets said out loud because a judge can tell the difference.

## Prize lanes worth aiming at

- **Taskmaster** track: a complete workflow, not a chatbot
- **Individual/Hobbyist**, two prizes of $10,000, which rewards nothing about enterprise credibility
- **Startup Excellence**, $20,000, needs an incorporated organisation with a corporate email. The US
  C-Corp and the onenept.com address qualify, and nobody had checked this category
- **Best Multimodal UX**, $5,000, which Build 2 aims at directly
