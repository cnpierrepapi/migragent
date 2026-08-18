# The brand pack, in plain words

Written before the interface, the same way `HOW_IT_WORKS.md` was written before the code. If the
built product ever contradicts this document, the document gets fixed rather than ignored.

Nothing here is claimed as checked unless it says how it was checked.

---

## The idea in one paragraph

The product has two moods and they are both true at once. Starting an application is a hopeful,
slightly nervous thing that a young person usually does, so the daytime face is bright and open. The
thing it hands back is a document that has to survive being read across a desk by a bank officer or
a registrar, so the night face is quiet, tight and grown up. Rather than fight that, the two faces
are split across the two themes: **light is bright and youthful, dark is elite and mature.**

The trick is that almost none of the difference is colour. It is geometry. Dark has less corner
radius, thinner rules, tighter letter spacing, a lighter display weight and slightly less air. Light
is rounder, looser and warmer. Someone flipping the toggle should feel the product grow up.

---

## The mark

Three candidates are drawn and sitting in `web/brand/`. Open `web/brand/preview.html` in a browser
and judge them at sixteen pixels, because that is the size that actually decides it.

**A. The gate.** An M whose middle stops short, so the space underneath it is a doorway. A dot
stands in the doorway, and that dot is a footnote marker. It says the two things the product is: you
are going through a door, and nothing gets said without a source. One colour, no gradient, no
lettering to break at small sizes.

**B. The stamp.** An entry stamp landed slightly crooked, with a chevron for the crossing. The
warmest and the fastest to read. The problem is that it is crowded: every immigration brand already
owns a stamp, and a judge who has seen ten submissions will have seen four stamps.

**C. The footnote.** Three lines of a claim and the raised marker that proves it. The most honest of
the three, and the least obvious. It says nothing about travel at all, which is either the weakness
or the whole point.

**The recommendation is A.** It is the only one that carries the citation rule in the shape itself,
and it is the only one that stays clearly itself at favicon size. This has not been tested on anyone
but me, so it is a recommendation and not a finding.

### Favicon

`web/brand/favicon.svg`. An SVG favicon can answer `prefers-color-scheme`, which a `.ico` cannot, so
the icon is deep green on warm paper by day and raised green on near black by night. A PNG fallback
gets generated when the web app exists and not before.

---

## Colour

Two palettes, in `web/brand/tokens.css`. The comment beside every colour carries its measured
contrast ratio against the paper it sits on.

Those ratios came from `python tools/contrast.py`, which was written and run before the numbers were
written down. This is the rule from `INHERITED.md` applied to design: no claim in a document before
the test that proves it. A palette that says "accessible" without a measurement is exactly the kind
of untested claim that went wrong last time.

**Measured on 18 August 2026, light:**

| Pair | Ratio | What that permits |
| --- | --- | --- |
| ink on paper | 16.93 | body text anywhere |
| ink soft on paper | 5.75 | body text |
| primary on paper | 6.00 | body text, buttons, the mark |
| primary hot on paper | 3.17 | **large text and fills only, never body** |
| link on paper | 5.62 | body text, and it is the colour of a real source |
| warn on paper | 5.30 | body text, marks an open question |
| accent on paper | 1.51 | **decoration only, never text of any size** |

**Measured the same day, dark:** every pair clears 6.40 and most clear 9.00, because a dark ground
gives contrast away cheaply. The lowest is warn at 6.40. The full table is the output of the script.

Two rules fall out of the numbers rather than out of taste. The light amber is a highlighter and can
never carry a word. The light bright green is a hover and a fill, not a paragraph.

The mature move in dark is dropping the amber to an aged gold and letting the green rise. Same two
roles, ten years older.

### Why green

The obvious choices are blue for trust and red for flags, and both are taken by every government
portal and every visa consultant. Green here means cleared, which is the feeling the product is
selling, and it reads as approval on a document without shouting.

---

## Type

- **Display: Fraunces.** A variable serif with a SOFT axis and a WONK axis. Set soft and heavy it is
  friendly, set flat and light it is serious. One family that genuinely does both moods is why it
  beat pairing two different serifs, and one fewer font is one fewer thing to embed in a PDF.
- **Body and interface: Inter.** Correct, boring, everywhere, and it has real tabular numerals,
  which matter because half of this product is money and dates in columns.
- **Sources, dates and hashes: IBM Plex Mono.** A source link is evidence, so it is set as evidence.

All three are open licensed and self hostable, which matters because the PDF renderer runs on Cloud
Run and cannot depend on a font CDN being reachable.

---

## How it talks

Second person. Present tense. Short sentences. Exact numbers.

**Say:** what a page said, and when it was read. "Read on 18 August 2026." "No official source found
for this."

**Never say:** seamless, empower, unlock, revolutionise, effortless, journey. Never "AI powered".
Never a guarantee of an outcome. Never "legal advice", because it is not, and saying it is invites a
problem this product does not need.

**No em dashes anywhere in shipped copy**, per the standing rule.

**Three phrases the product owns and repeats on purpose:**

1. "Nothing is stated without a source."
2. "Read on [date]." Attached to every requirement, every time.
3. "Open questions." The honest name for the back of the guide.

The tone is a competent friend who has already read the website, not a consultant and not a robot.
The most persuasive sentence available is a true one with a link on it.

---

## Motion

One animation earns its place: **the run**. One line lands per source, carrying the address and the
moment it was read, and a counter ticks the real number. It is the whole product made visible in
four seconds, and it is what the hackathon video opens on.

Everything else is 120ms to 200ms on one easing curve. No parallax, no scroll hijacking, no counting
up to a number that is not the real number, no skeleton shimmer pretending to be work. Every
animation stops under `prefers-reduced-motion`, which is already wired into `tokens.css`.

The restraint is not modesty. A product whose pitch is that it does not invent things cannot have an
interface that performs activity it is not doing.

---

## Photography

Photorealistic and deliberately quiet. Documentary, natural light, muted, nobody smiling at a
camera. A hand resting on a paper form at a kitchen table. A printed guide on a desk next to a
closed passport. A bank counter from behind the queue. An empty embassy waiting room chair.

**Hard rules, because this is the category where generated images do damage:**

- No real government crest, seal, letterhead or logo. Not one.
- No readable passport page, no visible document number, name or photograph.
- No recognisable real person, and nothing that reads as a specific named country's officialdom.
- No airplane windows, no globes with pins, no suitcase silhouettes, no diverse group high fiving.
- Every generated image is labelled as an illustration in the repo, so nobody can later mistake one
  for evidence of anything.

Not generated yet. Waiting on the mark being chosen, because the grade follows the palette.

---

## The first SEO post

One post, not a content plan.

**"Canada study permit proof of funds: every change since 2024, with the source for each."**

It is chosen because it is the deep lane, because the figure genuinely moved more than once, and
because it is the only piece of writing that a competitor cannot copy without doing the same work.
It is also the public face of the change line, which is the part of the product somebody renews for.

**It gets written after Build 3 exists**, from the registry, with real sources and real dates. A
post about how honest the change tracking is, published before the change tracking runs, would be
the exact mistake this project keeps writing down and promising not to make.

---

## Pricing

As given on 18 August 2026, recorded verbatim before it gets tidied.

**Free.** The first agent run. The full guide, sources on every line, saveable as a PDF.

**$14 a month.** Three reruns. A daily digest across the watched sources, filtered to the ones
that touch your case. Up to seven applications filled out for you, school, job or exam.

**$105 per case.** Done for you, plus a visa checklist, with third party services arranged.

The period was settled on 18 August 2026: the middle tier is a monthly subscription, the top tier is
charged once per case. So the two tiers are different objects rather than two sizes of the same
thing. The monthly one renews because the sources keep moving, which is the daily digest doing the
work. The per case one ends when the case ends.

That has one consequence worth writing down now. Somebody paying $105 for one case is not
subscribed, so they get no digest once the case closes, and the guide they hold goes stale exactly
the way the guides this product exists to replace go stale. Either the per case tier carries the
watch for the life of the case and says so, or it says plainly that it does not. It cannot be left
unstated, because going quietly stale is the failure the whole product is aimed at.

### Two things about the pricing still to settle before any of it is coded

**1. "Tracking the 100 plus sites" cannot be written until 100 sites exist.** The standing rule for
this build is that the source count shown is the real one. So the number on the pricing page is
rendered live from the Firestore registry, and on the day it is nine it says nine. If the registry
reaches 100 before submission, the copy says 100 because it is true, not because it was written in
advance. This is worth more than the marketing, since the whole pitch is that this product does not
overstate.

**2. "Applications filled out for you" needs a line drawn through it, and this is a real
constraint rather than caution.** Filling out a school, job or exam application for someone is
ordinary form preparation. Doing the same for an immigration application, for a fee, is a different
thing: Canada restricts paid immigration representation to authorised people, and the $105 tier as
worded sits near that line. The fix is framing rather than product. MIGRAGENT prepares documents and
checklists and hands off to a licensed third party for anything that counts as representation, which
appears to be what "third party services" already meant. It needs to be explicit in the copy, on the
pricing page and in the terms, before money is taken.

Nothing here is in Builds 1 to 4. Payment is not in the hackathon scope and does not go in before
the 31st. The brand pack carries the pricing so the design is right, and the plumbing waits.

---

## Where the files are

```
web/brand/tokens.css        both palettes, both geometries, ratios in the comments
web/brand/logo-a-gate.svg   candidate A, recommended
web/brand/logo-b-stamp.svg  candidate B
web/brand/logo-c-footnote.svg candidate C
web/brand/favicon.svg       theme aware, follows whichever mark is chosen
web/brand/preview.html      open this in a browser, toggle it, judge the marks at 16px
tools/contrast.py           the measurement behind every ratio quoted above
```
