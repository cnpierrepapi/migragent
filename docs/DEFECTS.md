# Defect log

Every bug and its fix, written when it happens rather than reconstructed later. A defect stays open
until something has actually been run that proves it closed, and the log says what was run.

---

## D1. A code comment claimed an isolation that does not exist yet

**Found:** 18 August 2026, reading `migragent/identity.py` before starting Build 1.

**What it said.** The module docstring stated that a claim like "the reader cannot write" is
"enforced by Google rather than by our code choosing to behave."

**Why that was wrong.** The four service accounts exist and hold no roles at all. Nothing is
enforced, because there is nothing to enforce. Checked with:

```
gcloud projects get-iam-policy project-e0928f2f-5abf-46a3-b8a --format=json | grep -c "migragent-"
```

which returned `0`. All four accounts confirmed present with
`gcloud iam service-accounts list`, so the accounts are real and the bindings are absent.

**Why it matters more than a stale comment.** This is the same failure that `INHERITED.md` records
from the previous build, where the docs asserted an isolation guarantee that was not true when it
was written and was read and believed before anyone tested it. It arrived here by being copied
across with the file.

**Fix.** The docstring now says what is true today, names the two things that have to happen before
the stronger sentence goes back, and says where the check lives. The strong claim gets restored only
after roles are granted and a test has proved a denial.

**Status:** open. It closes when the least privilege grants exist and a test shows the researcher
being refused a write. That test is the first task of Build 1.

---

## D2. The mark turned to mush at favicon size

**Found:** 18 August 2026, looking at `web/brand/preview.html` in Chrome rather than trusting the
drawing.

**What was wrong.** Candidate A carried the comment "still legible at 16 pixels", which was written
at the same time as the shape and had not been looked at. It was not true. The M's legs ended at
y=55 and the footnote dot sat at y=51 with radius 4, so both shapes occupied the band from y=47 to
y=55. Rendered at 16 pixels they merged into a single blob and the dot stopped reading as a dot.

**How it was found.** The preview was served on localhost, opened in Chrome, and the row of marks at
60px, 28px and 16px was magnified. The 16px gate was visibly a smudge. The stamp survived the same
test unchanged.

**Fix.** Legs lifted to end at y=45 and the dot dropped to y=56 with radius 5, in
`logo-a-gate.svg`, in `favicon.svg` at its own proportions, and in all four inline copies inside
`preview.html`. Re-served, reloaded and magnified again: the dot now separates cleanly at 60px, 28px
and 16px.

**Note.** This is the same species as D1. A sentence describing a property was written next to the
thing before anything had checked the property. It is a cheap example, which is exactly why it is
worth logging: the habit is what matters, not the size of the bug.

**Status:** closed, verified by eye in Chrome at all three sizes on 18 August 2026.

---

## D3. Every Imagen endpoint 404s on this project

**Found:** 18 August 2026, generating the photographic set.

**What happened.** `imagen-4.0-generate-001` and `imagen-3.0-generate-002` both returned 404 at
`us-central1`, with "not found or your project does not have access to it". Then
`gemini-3-pro-image-preview` returned 404 at both `us-central1` and `global`.

**What works.** `gemini-2.5-flash-image` returned 200 at both `us-central1` and `global`, using
`generateContent` with `responseModalities: ["IMAGE"]` rather than the Imagen `:predict` shape.

**Why it is logged.** It is the same shape as the Gemini 3.5 gotcha already in `INHERITED.md`: a
model name that reads as current is simply absent on this project, and the error says nothing useful
about which one to reach for. The next person needs the working name and the probe, not a guess.
`tools/make_images.py` carries the working endpoint and the date it was probed.

**Also fixed on the way.** `subprocess` could not launch `gcloud` on Windows because it is a `.cmd`
wrapper, so `CreateProcess` raised `WinError 2`. Resolved with `shutil.which` rather than
`shell=True`.

**Status:** closed. Six images generated.

---

## D4. A generated image broke the image rules written two hours earlier

**Found:** 18 August 2026, looking at the generated set rather than filing it.

**What happened.** `docs/BRAND.md` bans a government crest and any readable document in the
photography, and the generation prompt carried those bans in words. The desk shot came back with a
passport cover carrying a gold emblem and embossed lettering. The emblem belongs to no real country,
which is not a defence: a made up crest on the marketing page of a product that sells not inventing
things is the worst possible place for one.

**Why it happened.** The prompt named a passport, and asked the model not to draw what a passport
has on it. Naming the object was the mistake, not the ban.

**Fix.** The shot was rebuilt with no passport in the frame at all, a plain unmarked folder in its
place, and the prompt now says so explicitly. Regenerated and checked: no emblem, no lettering.

**Note on the rest of the set.** The bank counter shot has wall signage and a small wall notice, both
too soft to resolve into any word or mark. That is inside the rule, which is about anything readable
or attributable, and it is recorded here so the judgement is visible rather than assumed.

**Status:** closed, every one of the six looked at individually on 18 August 2026.

---

## D5. The isolation test passed while proving nothing

**Found:** 18 August 2026, on the very first run of `tools/test_isolation.py`.

**What happened.** There are no application default credentials on this machine, so every check
raised `DefaultCredentialsError`. Three checks correctly reported FAIL. The fourth, "web CANNOT
become the watcher", reported **PASS**, because it was a negative check and its `except` branch
treated any exception as the boundary holding.

Then the summary printed `4 of 4 passed`, because it counted anything not marked FAIL as a pass.

**Why this is the worst kind of bug for this project.** It is a test that produces evidence for a
security claim while testing nothing at all. It would have gone green in CI on a machine with no
credentials, and the sentence it exists to justify would have gone back into `identity.py` on the
strength of it. That is D1 all over again, only with a green tick in front of it.

**Fix.** A third verdict, `UNPROVEN`, distinct from both pass and fail. Missing credentials are
detected specifically (`google.auth.exceptions.DefaultCredentialsError`) and can never be read as a
boundary holding. The summary counts the three separately and prints unproven checks in full. The
exit code is zero only when something actually passed and nothing failed and nothing was unproven.

**Status:** closed. Verified by re-running with credentials still absent: it now reports
`0 passed, 0 failed, 4 unproven, of 4` and exits 1.

**Still open behind it:** the isolation itself is unproven until the test runs with credentials.
D1 stays open until then.

---

## D6. Hash-first would never have fired

**Found:** 18 August 2026, testing the fetcher against real pages rather than a fixture.

**What happened.** Two fetches of the same canada.ca study permit page, seconds apart, produced
different sha256 digests. Every time.

**Why it matters.** Rule 14 says a byte-identical page stops the round: no diff, no model call, no
cost. That rule is the entire cost model of the watcher, because most government pages do not change
most days. A digest that never matches means the watcher calls the model on every page every day
forever, and the daily bill becomes an inference bill instead of a fetch bill. The feature would
have looked like it worked, because nothing errors. It would just have been silently paying.

**Cause, found by diffing rather than guessing.** The two responses differ by exactly one line out
of 544: an Akamai mPulse beacon `<script>` carrying a per request nonce.

**Fix.** `stable_digest()` strips script blocks, style blocks, HTML comments and nonce style
attributes, collapses whitespace, then hashes. Both digests are kept on the result: `sha256` is the
stable one that change detection compares, and `raw_sha256` is the digest of the exact bytes written
to the snapshot, so the stored file can still be shown untampered.

It deliberately does not try to find "the main content". A heuristic that guesses which part of a
page matters is the mistake recorded in `INHERITED.md`, and a stripped-and-collapsed page is a text
substitution rather than an opinion.

**Verified both directions**, because only checking that the digest stabilises would have been half
a test:
- two consecutive fetches now produce the same stable digest, while the raw digests still differ
- editing one phrase in the body changes the stable digest

**Status:** closed.

---

## D7. Australia blocks the crawler even though robots.txt allows it

**Found:** 18 August 2026, on the first real fetch of three government pages.

**What happened.** `immi.homeaffairs.gov.au` returned **HTTP 403** to a polite, identified request.
Its robots.txt allows the path. canada.ca and gov.uk both returned 200 for the same fetcher.

**What it is not.** Not a bug, and not something to work around. Rule 10 stands: we do not disguise
the crawler to get past a server that does not want it.

**What it means for the build.** This is the "official site cannot be read" branch in
`docs/SOURCES.md` firing on a government source rather than a school, on day one, for a jurisdiction
we committed to. The Australia study lane needs another readable official source, and if there is
not one the lane says so plainly in the form rather than being quietly listed as covered.

**Status:** open. It is a source problem, not a code problem, and it is recorded so the Australia
lane is not marked deep on the strength of a page nobody could read.
