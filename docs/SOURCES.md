# The source registry

What MIGRAGENT reads, how it decides it is allowed to read it, and how a page becomes a citation.

The registry is **data, not code**. A source is a row. Adding source 400 is a write, not a deploy.
That is the only reason a count of sources can be an honest claim rather than a marketing number.

---

## Jurisdictions

Seven, set on 18 August 2026. Each one carries two lanes, **work** and **study**.

| Jurisdiction | Language of source | Note |
| --- | --- | --- |
| United Kingdom | English | |
| United States | English | |
| Canada | English, some French | the first lane built deep |
| Australia | English | |
| France | French | needs translation |
| Spain | Spanish | needs translation |
| United Arab Emirates | Arabic and English | official English versions usually exist, prefer them and record which was read |

Seven jurisdictions times two lanes is fourteen government source sets, plus the schools below.

### What this does to the plan

The original plan built Canada deep and offered two other lanes. Seven jurisdictions is a much
larger surface, and it is worth being straight about which part of it is cheap and which is not.

**Cheap:** the registry itself. Fourteen lanes and several hundred school pages are rows, and the
fetching, hashing and snapshotting is the same plain code for all of them.

**Not cheap:** extraction depth. Every lane needs its requirements checked by a person the first
time, because that is the difference between a guide and a plausible-looking list.

So the registry covers all seven from the start, the watcher watches all seven from the start, and
**extraction depth lands lane by lane.** The form says plainly which lanes are deep and which are
only being watched. A lane that is watched but not yet extracted is not hidden, and it is not
dressed up as finished. That is the same cut rule as before: lane depth flexes, rigour does not.

---

## Schools

For each jurisdiction, the fifty institutions with the highest international student enrolment.

### Picking the fifty, and citing the pick

"The top fifty" is itself a claim, so it carries a source and a year like every other claim.

1. Look for the most recent published international enrolment data. Start at 2025.
2. **If 2025 is not published, step back one year and look again. Repeat until data is found.**
3. Record the year found and the publisher, and store both on every school row.
4. Take the top fifty by international enrolment from that data.

The guide never says "the top fifty universities". It says the top fifty by international student
enrolment, according to a named publisher, for a named year. If the newest data available is 2023,
it says 2023. **The year is never rounded forward and never left off.**

### Finding the official page

The target is always the institution's own site, because a third party page is somebody's summary
and a summary is where invented requirements come from.

1. Go to the institution's own domain and find the admissions or international requirements page.
2. **Check robots.txt before fetching. If it disallows the path, that is the end of it.** No
   fetching anyway, no pretending a rule is advisory, no changing the user agent to get around it.
3. If the official site cannot be read, the school is recorded as **not readable, with the reason**,
   and it does not silently vanish from the count.
4. Where a school is first discovered through an aggregator, the aggregator is a **lead, never a
   citation.** For example a course found on a portal site is used only to work out which university
   and which programme, and then the university's own page is located and read. The portal never
   appears as the source of a requirement.
5. Inside a readable official site, follow the institution's own links to the pages that carry the
   detail: entry requirements, English language requirements, fees, deadlines.

**A lead is how we found it. A source is what we read.** Those are two different fields on the row
and they are never collapsed into one.

---

## Translation, and why it does not touch the citation

France and Spain publish in French and Spanish. The UAE publishes in Arabic and English.

The naive order is translate the page, then extract requirements from the translation. That is
wrong, and it is wrong in the specific way this product cannot afford: a translation error becomes
an invented requirement with an official link sitting next to it, which is worse than no answer.

**The order is:**

1. Fetch the page in its original language, and snapshot it.
2. Extract the requirement **from the original language**, and keep the original sentence verbatim.
3. Translate for display only.
4. Store the original sentence, the translation, and the fact that it is a translation.
5. The guide shows the translation, and shows the original quote underneath it.

So the citation is always the original page, in its own language, with the sentence it came from. A
reader who speaks the language can check us. A reader who does not can see exactly what was
translated rather than trusting that something was.

Anything that cannot be translated with confidence goes to open questions like any other gap. An
uncertain translation is a missing source, not a soft one.

---

## What a row holds

Every source in the registry carries at least this:

- jurisdiction, lane (work or study), and whether it is a government or an institution
- the URL actually fetched
- the language of the page
- how it was discovered, and the lead if there was one
- what robots.txt said, and when that was checked
- the date and time it was last read, and the hash of what came back
- where the snapshot is stored
- for a school: the enrolment data publisher and the data year behind its place in the fifty
- if it is not readable: the reason, in words

---

## Politeness, which is not optional

- robots.txt is checked before the first fetch and re-checked on a schedule. It is a gate.
- The crawler identifies itself honestly, with a contact address.
- One request at a time per host, with a gap, and it backs off when asked to.
- Hash first. A byte-identical page stops right there: no model call, no cost. Most government pages
  do not change most days, so a daily round is mostly fetches, and the bill stays a fetch bill.
- Snapshots are kept because "read on this date" means nothing without the page behind it.

---

## The count

The number of sources shown anywhere in the product is a live count from the registry.

On the day it is nine it says nine. On the day it is four hundred it says four hundred. It is never
written into copy in advance, and it is never rounded up to a friendlier number.
