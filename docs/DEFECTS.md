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
