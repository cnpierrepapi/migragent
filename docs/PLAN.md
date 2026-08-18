# The plan

Three builds. Everything that has been asked for is in one of them. Each ends with something working
on a live URL.

Standing rules are in `docs/RULES.md`. What gets read and how is in `docs/SOURCES.md`. How it feels
to use is in `docs/HOW_IT_WORKS.md`.

**Where it lives:** Cloud Run, service `migragent`, at `migragent.onenept.com`. Firestore, Pub/Sub,
Cloud Scheduler, Cloud Storage. The app holds passports and a service account, so nothing is
exported to another provider.

---

## Build 1 — The guide, end to end

**Ends with:** fill in the form on the live URL, get a PDF with real requirements and real citations.

**Foundation**
- Least privilege roles on `migragent-researcher`, `migragent-writer`, `migragent-watcher`,
  `migragent-web`, and a test that shows the researcher refused a write. Closes D1.
- Cloud Run service, deploy path, `/health`, domain mapping to `migragent.onenept.com`.

**The registry, as data**
- Firestore collection, one row per source. Seeded with seven jurisdictions times two lanes:
  UK, US, Canada, Australia, France, Spain, UAE, each with work and study.
- Row carries URL, language, discovery, robots state, last read, hash, snapshot location,
  provenance.

**The reader**
- Fetcher in plain code: robots.txt gate, fetch, hash, snapshot to Cloud Storage, stamp the date
  read. Identifies itself, one request per host at a time, backs off.
- Researcher on ADK: reads the page, decides whether a sibling page is needed, fetches it, stops when
  the requirement is complete. This is the only place ADK appears.
- Extraction with Gemini. The citation is attached from the fetch, never from the model.
- Translation path: extract from the original language, keep the original sentence verbatim, store
  the translation as a translation.

**The output**
- Intake form: jurisdiction, lane, situation. Says plainly which lanes are extracted deep and which
  are only watched.
- Guide: ordered steps, dependencies, cost, duration, source and date read on every line, provenance
  label, open questions at the back.
- Rendered as a document and downloadable as PDF, with self-hosted fonts.
- Live source count on screen, read from the registry.

---

## Build 2 — Documents, the score, and the fillable form

**Ends with:** uploading a transcript changes the guide, moves a real number, and returns a form
built for your case.

**Uploads**
- Passport, transcript, degree, English test, registration, employment letters.
- Gemini reads them. This is the multimodal work.
- Data protection from the start: stated retention window, encryption, a delete-my-data path that
  actually deletes.

**The score**
- Coverage matching: which extracted requirements each uploaded document actually addresses.
- The readiness score is that coverage, not the upload count. Tapping it opens the breakdown.
- Documents listed by what they are worth, because a passport unlocks more than a school transcript.
- Threshold crossing fires the confetti and lights **GO**. Nothing fires under reduced motion.

**Gaps and routes**
- What is satisfied, what is missing, what is expiring.
- Every gap gets routes: accepted alternatives, cost, booking lead time, and which ones this
  regulator actually accepts.

**The school registry**
- Ranked by percentage of international students. Top fifty, or the top ten per cent of every
  registered institution where there are not fifty to take.
- Publisher and data year stored on every row, walking back from 2025 until real data exists.
- Three step route to a readable page: the institution's own site, then the course portal page, then
  drop and take the next one down. Dropped institutions recorded with the reason.

**The fillable form**
- Generated per case, asking only what is still unknown now that the lane and the gaps are known.
- Filling it feeds straight back into the guide.

---

## Build 3 — The watcher, the board, and the applications

**Ends with:** a daily round catches a real change, the board updates itself, and the drafts are
waiting.

**The watcher**
- Cloud Scheduler fires, Pub/Sub fans out, Cloud Run jobs fetch.
- Hash first. Byte-identical stops there.
- On a change: diff, Gemini explains what moved, both versions and both dates recorded with the
  source.
- The change line, seeded from published government change history with their dates.
- The country watch screen: where policy has loosened and where it has tightened, from the observed
  record. Read only first, personalised after.

**Accounts and memory**
- Firebase Auth.
- Per user in Firestore: case, documents, guide, watchlist, and what they have already been told so
  they are not told twice.

**The board**
- Kanban columns, populated from the guide's steps and from what the watcher finds.
- The agent drafts what it can: cover letters per job, CVs per school or role, one per application
  rather than one for everything.
- Every draft says it is a draft. Nothing is ticked off on the user's behalf.
- New tasks appear and stale ones are marked when a source moves.

**Notifications**
- Changes routed to the users they affect with embeddings and vector search, rather than running
  every source against every user.
- Browser push permission asked for properly, fired when a guide moves.

**Submission**
- Architecture diagram, README a stranger can follow, the video.

---

## The three mandatory requirements

| Required | Where |
| --- | --- |
| Gemini 3.5 or newer | requirement extraction, document reading, diff explanation |
| A Google agent framework | ADK, on the researcher only |
| Google Cloud infrastructure | Cloud Run, Firestore, Pub/Sub, Cloud Scheduler, Cloud Storage |

No marks exist for touching more Google products. Every service above earns its place, and the
restraint gets said out loud because a judge can tell the difference.
