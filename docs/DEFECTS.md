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

**Closed 18 August 2026.** `tools/grant_roles.sh` applied the roles and `tools/test_isolation.py`
reported **4 passed, 0 failed, 0 unproven**, exit 0:

```
PASS  researcher can read the registry: read succeeded
PASS  researcher CANNOT write: PermissionDenied, which is the point (403)
PASS  writer CAN write: wrote and cleaned up, so Firestore is reachable
PASS  web CANNOT become the watcher: refused: RefreshError
```

The third line is what makes the second one evidence. A denial while the database is unreachable
would look identical and mean nothing.

The claim is back in `identity.py`, and it names the test that earns it. It comes out again if the
test ever stops passing.

**One honest caveat, checked rather than waved at.** The fourth check runs as the developer's user
account, not as `migragent-web`, so on its own it proves that *that* principal cannot become the
watcher. `gcloud iam service-accounts get-iam-policy` on all four accounts settles the stronger
version: the watcher has **no `serviceAccountTokenCreator` bindings at all**, so no principal
anywhere can impersonate it. It runs as itself on its own Cloud Run job, reached through Pub/Sub.

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

---

## D8. A flaky local network nearly marked six working government sites dead

**Found:** 18 August 2026, probing alternative sources for the lanes that failed the first seed.

**What happened.** Six hosts returned `URLError: [Errno 11001] getaddrinfo failed`, including
`service-public.fr`, which had returned 383,307 bytes about a minute earlier. The fetcher recorded
each as `unreachable`, and the seeder was about to write that into the registry as a property of the
source.

**Checked rather than assumed.** Resolving all six hosts three times each immediately afterwards
gave 3/3 for every one of them. So the failures were transient and local, and the sources were fine
the whole time.

**Why it matters more here than in most code.** The registry is the product's memory. A row saying a
government page is unreachable would take that lane out of coverage, and the reason recorded would
have been wrong. Worse, it would have looked like diligence: a specific error, a timestamp, a source
marked honestly unavailable. Bad data with a citation on it is exactly what this product exists not
to produce.

**Fix.** Transport failures are retried three times with a growing backoff. Outcomes now separate
what the server said from what the network did:

- `refused` for 401, 403 and 429, which is the server answering, so it is final and about the source
- `unreachable` for 404 and 410, also the server answering
- `network_unknown` when nothing answered at all after every retry

`network_unknown` is deliberately **not** a blocked state in the registry. It sets
`unverified_reason` and leaves the row unverified, and `Registry.counts()` reports readable, blocked
and unverified as three separate numbers. A source we could not reach is not a source we know is
unavailable, and the count on screen should not pretend otherwise.

**Status:** closed. The re-run reported Spain as unverified rather than blocked, which is the
distinction working.

---

## D9. Spain's official sites failed TLS verification

**Found:** 18 August 2026, seeding the registry.

**What happened.** Both `www.exteriores.gob.es` and `extranjeros.inclusion.gob.es` failed with
`SSL: CERTIFICATE_VERIFY_FAILED, self-signed certificate in certificate chain`, consistently, across
retries. Every other jurisdiction verified fine.

**Diagnosed instead of guessed.** `openssl s_client` shows the chain ends at **AC RAIZ FNMT-RCM**,
the Spanish national certificate authority, run by the Fabrica Nacional de Moneda y Timbre. For
comparison, gov.uk chains to GlobalSign, which verifies without complaint.

That root is present in the installed certifi bundle, and the Windows trust store validates both
hosts without error. So this was never a missing CA. It is how Python's default context assembles
its chain on this machine.

**Fix.** The fetcher verifies against the operating system trust store via `truststore`, falling
back to the stock default context if that package is unavailable.

**What was deliberately not done.** Verification was not disabled, and no host was exempted. This
code fetches pages for a product that holds people's passports, and an unverified TLS connection to
a government site is not a shortcut worth taking to make a seed script look tidier. If the trust
store cannot be used, Spain fails loudly rather than being silently downgraded.

**Status:** closed. `exteriores.gob.es` now returns 200 and 163,798 bytes.

---

## D10. The registry held front doors and called them sources

**Found:** 18 August 2026, on being asked how fourteen sources could possibly cover seven
jurisdictions. It cannot, and the number was indefensible.

**What was wrong.** The seed registered one entry page per jurisdiction and lane. The seeder's own
docstring said "the researcher follows the site's own links from there", and that following had
never been built. So the registry held fourteen front doors while describing itself as a source
registry.

The requirements for a single study permit are spread across eligibility, funds, biometrics, medical
exams, fees, processing times, work rights and dependants. Each is a separate page with its own
last-updated date, which is exactly what a watcher needs to be watching.

**The first fix was also wrong, and measurably.** Discovery kept links that were on the same host and
either under the entry page's section path or linked directly from the entry page. On
`gov.uk/student-visa` that kept 55 of 68 links, nearly all of it global navigation: benefits,
driving, childcare, births and deaths. The section rule collapsed to the whole site because the
entry path has one segment, and the direct-link rule caught every menu item.

**Why the obvious repair was refused.** Filtering link text for words like visa, fees or eligibility
would have worked on that page and is a heuristic over names, which `INHERITED.md` records as the
mistake that once reported survey answers as decisions about people. It fails both ways: it misses a
page called "Before you apply" and collects a press release that mentions a visa.

**What works.** Navigation appears on every page of a site. Content does not. Intersecting the links
of two pages from the same host gives the furniture, and what survives is what makes a page
different from its neighbours. Measured:

- gov.uk: 68 links, 42 shared with a sibling page, **26 unique**, including `/student-visa/money`,
  `/student-visa/knowledge-of-english`, `/student-visa/documents-you-must-provide`
- canada.ca: 43 links, 33 shared, **10 unique**, including eligibility, get-documents, prepare, apply

**The cost, stated rather than hidden.** A host needs at least two known pages before anything on it
can be walked, so hosts with one entry point are skipped and the run prints which. Also, a walk this
wide picks up genuine tail pages that carry no requirement, such as customs and duty free pages
linked from the foot of a visa page. Those are recorded as pages read and simply yield no citations.
The registry counts pages read; the guide cites only what produced something. A wide walk therefore
cannot inflate the number of claims, only the number of pages we looked at.

**Status:** closed.

---

## D11. Seeding both Spanish lanes with one URL made the whole page look like navigation

**Found:** 18 August 2026, when Spain and France both returned zero pages from a walk that reported
no error.

**What happened.** Navigation is learned by keeping links that appear on two or more pages of a host.
Spain's study lane and work lane were seeded with the same consular URL, because I could only find
one Spanish page that fetched. So the sample held that page twice, every link on it appeared "on two
pages", the entire page was classified as furniture, and nothing survived.

**Why it is worse than returning nothing.** The run printed `9 navigation links learned` for that
host and then `0 new`, which reads like a site with nothing on it rather than a broken measurement.

**Fix.** Two parts, because either alone would leave the trap open.
- `learn_chrome` de-duplicates its sample and needs two *distinct* pages, not two entries.
- The Spanish work lane is seeded with a genuinely different page. The first replacement I chose
  404ed, so it was checked before it was kept.

**Status:** closed.

---

## D12. France was thrown away by a same-host rule

**Found:** 18 August 2026, same run.

**What happened.** France returned zero, and its navigation had been learned correctly. The reason
was the scope rule: candidates had to be on the same host as the entry page. France's entry page is
on `service-public.fr`, and everything it links to lives on `service-public.gouv.fr`,
`france-visas.gouv.fr`, `legifrance.gouv.fr` and `diplomatie.gouv.fr`. The site moved domains and
the old host mostly links forward to the new one.

Stripping navigation from the French page had actually worked and left 29 real links. The scope rule
then discarded every one of them.

**Fix.** Scope is now the jurisdiction's official government domain suffix rather than one hostname:
`.gouv.fr` for France, `.gov.uk`, `.gob.es`, `.gc.ca` and so on. That is structural, since it is a
fact about who operates the domain and is readable from the name, and it is not an opinion about the
words on the page. Anything outside those suffixes stays a lead and never becomes a source.

**Two follow-on bugs this created, both caught before the run:**

1. Widening scope means meeting hosts that were never in the seed sample, and an unsampled host has
   no navigation learned, so its menus came back looking like content. Chrome is now learned lazily,
   the first time a host's pages need judging.
2. The lazy sample first took the two candidates in document order, which on
   `service-public.gouv.fr` were the site root and the sign-in page. Those two share almost no links,
   so almost nothing was classified as navigation. The sample now takes the three deepest paths
   available, because deep paths are leaf content and shallow ones are menus, which again is a fact
   about how URLs are built rather than about what they say.

France went 0 to 83 with the scope fix, to 57 with lazy learning, and to 19 once the sample was
chosen properly. 19 is the honest number and the earlier two were menus.

**Status:** closed.

---

## D13. Six lanes reported exactly 44, which was the ceiling

**Found:** 18 August 2026, reading the first successful expansion.

**What happened.** The walk was capped at 45 pages. Six of the eight lanes that ran returned exactly
44 pages. That is not a measurement of anything, it is the cap with one page subtracted, and
reporting it as coverage would be the same class of mistake as counting front doors and calling them
sources.

**Why it matters here.** The count shown in this product is supposed to be real, per rule 5. A number
that is silently the ceiling is a number that means nothing while looking like it means something.

**Fix.** The cap is raised to 150 and exists only to stop a runaway walk. Any lane that reaches it is
reported as having hit the cap, rather than having its ceiling quietly presented as its size.

**Status:** closed.

---

## D14. Playwright did not unblock either blocked lane, and that is the answer

**Investigated:** 18 August 2026, on the question of whether a real browser could read the pages a
plain HTTP client could not.

**The two blocked lanes are not the same case, and the difference decides everything.**

`immi.homeaffairs.gov.au` publishes a robots.txt that **allows** the visa pages, then returns 403 to
a polite identified urllib request. Their own machine-readable crawl policy says yes and something
in front of the site refuses anything that does not look like a browser. Rendering the page in a real
browser there is meeting their transport, not getting around their policy.

`travel.state.gov`, `uscis.gov` and `studyinthestates.dhs.gov` **disallow** the pages in robots.txt.
A browser does not change that answer. Using one there would be precisely the "no fetching anyway,
no changing the user agent to get around it" that rule 10 rules out.

**So `migragent/render.py` checks robots before it opens a page**, and refuses a disallowed URL
itself rather than trusting the caller to remember. Verified: the US page returns
`blocked_by_robots` with the reason, and no request is made.

**Result for Australia: still 403, to a real Chromium carrying our honest MIGRAGENT user agent.**

The obvious next move is to send Chrome's own user agent string and get in. That is refused. It
means passing ourselves off as a person browsing in order to collect a page, and this product's
entire claim is that its records are true. A site that refuses our identified client has given a
clear answer, and the answer is taken. Australia stays recorded as `server_refused`, with the reason,
and reaches its lanes through the portal fallback in `docs/SOURCES.md` or not at all.

**Does the browser earn its place anywhere?** Measured, on pages that a plain fetch already reads,
comparing visible text:

| source | plain | rendered | change |
| --- | --- | --- | --- |
| service-public.fr | 28,494 | 35,643 | **+25%** |
| gov.uk | 9,265 | 9,536 | +3% |
| u.ae | 1,357 | 1,293 | -5% |
| exteriores.gob.es | 13,724 | 5,373 | -61% |

France gains real content that only exists after scripts run. Spain's drop was checked rather than
assumed: rendered and plain both open with the same real content, so that is duplicated menu markup
being collapsed and not a consent wall swallowing the page.

**Decision:** the browser is kept and used selectively, where a source is refused a plain fetch or
where rendering demonstrably yields more for that source, and the method used is recorded per
snapshot. It is not a blanket replacement, because on three of four hosts it costs time and returns
the same page or less.

**Status:** closed as investigated. Australia and the United States both remain blocked, honestly.

---

## D15. Spain walked to zero three times, and the cause was never where I looked

**Found:** 18 August 2026, after the third consecutive run in which Spain reported zero pages.

**The two earlier explanations were both real bugs and neither was this one.** D11 was the duplicated
seed URL, which was genuinely broken and genuinely fixed. Fixing it did not move Spain off zero. The
run then said `9 navigation links learned` for `exteriores.gob.es` and `0 new`, which I read as a
thin site rather than as a measurement that could not possibly work.

**The actual cause.** That page serves **9 links** to a plain HTTP client and **117** to a browser.
Its navigation and its content links are written by scripts. With nine links total, and navigation
learned by keeping links that appear on two pages, essentially every link was classified as
furniture and nothing could survive. The site was never thin. We were never seeing it.

**Why it took three runs.** Each time there was a real bug in front of it that explained the symptom
well enough to stop the search. A plausible cause that is also true is the hardest kind to look past.

**Fix.** The expander decides per host whether pages have to be rendered, by measuring: if a plain
fetch yields fewer than 25 links, it renders one page and compares. Spain crosses that by a wide
margin, gov.uk and canada.ca never trigger it. The decision is cached per host, so a site is tested
once rather than on every URL, and rendering stays the exception.

Verified on the next run: `exteriores.gob.es` learned **113** navigation links, up from 9.

**What this changes about D14's conclusion.** That entry said the browser unblocked neither blocked
lane, which is still true for Australia and the United States. It missed a third case entirely: a
site that fetches fine, returns 200, and hides its links behind scripts. That case does not look
blocked at all, which is what makes it worse. The browser earns its place on Spain, not on the two
lanes it was built for.

**Status:** closed.

---

## D16. A moved seed URL left an orphan that walked as an extra entry point

**Found:** 18 August 2026, in the same run: `11 readable entry points` where fourteen candidates
minus four blocked is ten.

**What happened.** Spain's work lane was re-seeded onto a different page. Rows are keyed by a stable
id derived from the URL, so the new URL wrote a new row and the old one stayed. The purge before a
re-walk removed rows discovered by walking and left seed rows alone, so the orphan survived, was
counted as readable, and walked as an eleventh entry point reporting its own zero.

**Fix.** The purge now also removes seed rows whose id is not in the current seed list, so the
registry holds the seed that exists rather than every seed that ever existed. Verified: the next run
purged 857 rows and reported ten entry points.

**Status:** closed.

---

## D17. The quote check caught its first real one in production

**Not a defect in the build. Recorded because it is the first evidence the mechanism fires on real
traffic rather than on a test I wrote to make it fire.**

**18 August 2026.** The deployed service reports, from live counts:

```
1046 sources in the registry · 79 pages read · 422 requirements ·
1 dropped for having no quote on the page
```

Until now the drop count had been zero across every page read, which is a number that can mean two
opposite things: the model is behaving, or the check is not running. The synthetic tests in
`docs/DECISIONS.md` showed it rejects invented requirements, altered numbers and stitched fragments,
so the mechanism was proven. It had still never rejected anything real.

One in 423 is now on the record, dropped and counted, and the number is on the front page rather
than in a log.

**Why it is worth its own entry.** A guard that has never triggered is indistinguishable from a
guard that is switched off, and the difference only shows up on the day it matters. The drop count
is displayed permanently for that reason. If it goes back to a flat zero for thousands of pages, the
right response is to suspect the check rather than to congratulate the model.

**Status:** working as designed, and now demonstrated on real pages.

---

## D18. One bad page ended a whole extraction run

**Found:** 18 August 2026, reading the shells after a UK extraction over 60 pages.

**What happened.** Two thirds of the way through, Firestore returned
`503 ... Network is unreachable`, the exception escaped the loop, and the run died taking every
remaining page with it. The same transient flakiness is already recorded as D8.

**Why it matters.** These runs are long and they run over somebody else's network. A run that cannot
survive one bad minute will meet one, and losing forty pages of work to a blip that cleared by itself
is avoidable.

**Fix.** Each page is now attempted inside its own try, a failure is recorded and skipped rather than
raised, and the run prints what it lost at the end instead of the summary quietly describing fewer
pages than were asked for.

**Status:** closed.

---

## D19. The quote check shredded seven correct fields, because the haystack was noise

**Found:** 18 August 2026, on the first real document upload.

**What happened.** A specimen letter of acceptance uploaded as a PDF. The model read it correctly,
identified it as an `offer_letter`, and returned seven fields. **All seven were dropped** for having
quotes that were not in the document, and the score came back 0%.

**The cause was not the model.** `extract_text` pulled everything between round brackets out of the
raw PDF bytes. Chromium writes its content streams compressed, so that regex returned **12,146
characters of binary**. The code then saw a long non-empty string, set `text_layer = True`, and
checked every true quote against garbage.

**Why this is the worst kind of failure in this build.** Every other defect here has been a claim
that was not true. This one is the opposite: the guard against untrue claims, working perfectly, on
evidence that was itself wrong. A check with a corrupt haystack is not a check, it is a shredder,
and it destroys exactly the correct answers it exists to protect. It also fails silently and looks
like diligence: seven dropped fields reads as the model misbehaving.

**Fix, in two parts, because either alone leaves the trap open.**

1. Real extraction, with `pypdf`, which returns 437 characters of actual words for the same file.
2. `looks_like_text()`, which the extracted text has to pass before it counts as a text layer:
   at least 20 characters, at least 90% printable, at least 35% letters. Anything else is treated as
   no text layer at all, which sends the fields down the honest unverified path rather than the
   shredder.

**Verified both ways.** The guard rejects the exact binary string that caused this, and accepts
ordinary prose. The same upload now returns seven fields, all seven verified against the text layer,
nothing dropped.

**Status:** closed.

---

## D20. One rate limit, three symptoms that looked like three different bugs

**Found:** 19 August 2026, on the first end to end run of the new flow.

**What it looked like.** Three unrelated failures in one run:

- the uploaded document read back with zero fields and `error: HTTPError`
- two of four route searches reported "the route search failed: HTTPError"
- the form generator returned one question where it had produced twelve before

Three features, three shapes of failure. It read like the model behaving badly.

**What it was.** Every one of them was **HTTP 429, Too Many Requests.** A single run
fires five model calls back to back and none of them retried.

**Why it hid.** Five files each carried their own copy of the same twenty lines of
`urllib` plumbing, and each reported failures as `type(exc).__name__`, which for
every one of these was the string `HTTPError`. The status code, which was the
entire story, was thrown away before anybody could read it.

**Fix.** One caller in `migragent/model.py`, used by extraction, document reading,
coverage matching, route finding and form building. It retries 429, 500, 502,
503 and 504 with full jitter backoff, and it does not retry 400 or 403, because
those are answers rather than weather and retrying them just buries the message
more slowly. `ModelError` carries the status code and the first part of the
response body, so the next failure says what it was.

**Verified:** the same run now completes with the document read (7 fields, 7
verified), all four routes finding real options, and 11 questions generated.

**The lesson is about the error text, not the retry.** Missing retries cost a
failed run. An error message that discards the status code costs the next hour.

---

## D21. The word detector was reading the fields, not the document

**Found:** 19 August 2026, immediately after D20, when the working screen showed
"the words could not be checked: the strongest match only scored 1".

**What was wrong.** The detector is supposed to weigh a document's own vocabulary
against what the model called it. It was being run in `run.py`, on a string built
from field names, values and quotes, because by then the document's text no
longer exists. That is not the document. A letter of acceptance reduced to
`institution Example University of Testing` has almost none of the phrases the
detector looks for, so it scored 1 and declined to call anything, every time.

**Why it happened.** The text is deliberately never stored, per
`docs/DATA_PROTECTION.md`. So the only moment the words exist is inside
`DocumentReader.read`, and the detector was placed outside it.

**Fix.** Detection runs at read time on the real extracted text, and what is
stored is the verdict rather than the text: the detected kind, the reason, and
whether it agrees with the model. That keeps the data protection promise intact
while making the check mean something.

**Verified:** the same file now returns model `offer_letter`, words
`offer_letter`, scored 7 on 5 phrases including "letter of acceptance",
"designated learning institution" and "tuition fee", and the two agree.

**Worth noting:** a check that never fires and a check that always says "cannot
tell" fail the same way. Both look like caution and are silence.

---

## D22. One Spanish page counted six times, once per interface language

**Found:** 19 August 2026, reading the output of the first full extraction round.

**What was wrong.** Spain's consular site serves the same procedure page at six URLs that differ only
by a `/language/` segment: `es_ES`, `ca_ES`, `eu_ES`, `gl_ES`, `fr`, `en`. The walk found all six.
The registry counted all six as sources. The extractor read all six and produced six near identical
copies of every requirement on the page.

**Three separate costs, and the first is the one that matters.** It inflates the source count, which
is the single number on the front of this product that has to be true. It pays the model six times
for one page. And it would have put six copies of one requirement into a guide.

**Fix.** `Registry.redundant_language` compares the language segment against the languages the
jurisdiction actually publishes in, which the registry already records. Spain publishes in Spanish,
so the Spanish page is the source and the other five renderings are the same source wearing a
different interface.

**Nothing was deleted.** The ten rows are marked `blocked = duplicate_language` with the reason in
words, per rule 11, because they are evidence that the walk found them. The 35 requirements already
extracted from them were retired with the same reason, so they stop reaching guides while the record
of having read them survives.

**Worth noting:** this was invisible while Spain was one of eight lanes nobody had extracted. It
appeared the moment the pipeline ran everything, which is the argument for running everything.

**Status:** closed.

---

## D23. The watcher reported that two thirds of the corpus had changed, and none of it had

**Found:** 19 August 2026, on the first real watch round, which is the round that was supposed to
prove the watcher could be trusted to run daily. It proved the opposite, which is why it was run.

**What it looked like.** 143 pages watched. **95 came back as changed, within hours of being read,
across the UK, France and the UAE.** Canada and Spain reported nothing.

**What it was.** Every one of the 95 had **zero added lines and zero removed lines**. The words were
identical. Only the bytes differed.

The stable digest strips scripts, styles, comments and nonce attributes, which was enough for Canada,
whose Akamai nonce is D6. It is not enough for everybody. Hosts vary markup per request, per region
and per cache edge, and a digest fetched from a Cloud Run container in us-central1 did not match one
fetched from a laptop for the same unchanged page.

**Why it is serious rather than untidy.** Each false change triggered a full re-extraction of the
page, so a watch round cost about what a first read costs, every day, forever. And a watcher that
cries change every day is worse than no watcher, because the person receiving the notifications
learns to ignore them, and the day something real moves they ignore that too.

**Fix, and the shape of it matters.** Chasing the digest until it is perfect is a game with no end,
because every host has its own idea of what to vary. So the digest stays what it always was, a cheap
first filter that avoids reading anything at all, and a second gate now decides whether anything
happened: read the stored version, diff the text, and if not one line of words moved then nothing
moved, whatever the bytes say. Only then is a snapshot stored, a change recorded, or the model called.

**The archive holds versions of a page, not readings of it.** A byte variant that says exactly the
same thing is not stored, because filling the evidence store with noise makes the real history harder
to find.

**The 95 change rows were deleted.** They record changes that did not happen, and the change screen is
built from that collection. Keeping them would have meant the first thing this product ever said about
what moved in immigration policy was ninety five things that did not.

**The lesson:** the test that catches this is running the round twice with nothing expected to change
and demanding a zero. Nobody would have found it by reading the code, and it would have shipped
looking like a working watcher.

**Status:** closed.

---

## D24. The robots gate asked in somebody else's name, and recorded the answer as a refusal

**Found:** 19 August 2026, while looking for real Spanish entry pages after Spain produced one
citable requirement.

**What was wrong.** `allowed()` used `RobotFileParser.read()`, which fetches robots.txt as
`Python-urllib` rather than as us, and which turns a 401 or 403 on that fetch into "disallow
everything" without saying so.

Spain's immigration portal serves **403 to `Python-urllib` and 404 to a client that says who it is.**
A 404 means there is no robots.txt, which is permission. So the entire portal, which is where Spain
actually publishes its residence and study requirements, was recorded as refusing us when it had only
refused a user agent we do not use.

**What it cost.** Spain was seeded against the foreign ministry instead, whose pages are navigation,
and produced 1 citable requirement while the same walk found 65 one hop out. The lane looked like a
crawler problem and was a permission problem wearing a crawler's clothes.

**What else it was hiding.** Two claims in the product were wrong in the same way.

- **The US is not disallowing us.** `travel.state.gov`, `www.uscis.gov` and `studyinthestates.dhs.gov`
  return 403 on robots.txt to every user agent tried. They will not state their rules at all.
- **Australia is not refusing our crawler outright.** `immi.homeaffairs.gov.au` serves its robots.txt
  happily to a generic client and 403s the one that names itself.

Both still end in not crawling, because a host that will not state its rules has not given
permission. But "robots.txt disallows us" was written in the README, in the plan and in the code, and
it was not true of either country. That is rule 3 territory: a claim that was never tested, sitting in
front of users.

**Fix.** robots.txt is now fetched the way every other page is fetched, by a client that identifies
itself, and three outcomes are kept apart rather than collapsed: the host stated its rules and they
are obeyed; there are no rules, which is permission; or the host would not tell us, which stops the
crawl and is recorded as a refusal rather than a prohibition.

**Checked for regressions before switching**, across all 14 hosts in the registry: 12 still allowed,
including `u.ae`, which has no robots.txt at all and was previously allowed through the accidental
path. Only the US and Australia hosts stop, now with an accurate reason.

**The lesson:** a gate that asks a question in somebody else's name gets somebody else's answer. The
cost here was not the crawl it blocked, it was the sentence it put in the README.

**Status:** closed.
