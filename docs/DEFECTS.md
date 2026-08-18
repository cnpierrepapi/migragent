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
