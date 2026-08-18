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

For each jurisdiction, the institutions with the **highest percentage of international students**.

### Percentage, not ranking and not headcount

This is a share, not a league table and not a raw count. A small institution where 40% of the
students are international ranks above a huge one where 8% are, even though the huge one has more
international students in absolute terms.

That is the right measure for this product. Somebody choosing where to apply cares whether a place
is used to people like them: whether the admissions office has seen their kind of transcript before,
whether the visa letters go out on time, whether they will be the only one. Share answers that.
Headcount just finds the biggest campus, and ranking answers a question nobody here is asking.

### How many, per jurisdiction

**The top fifty by international share**, except where there are not fifty to take.

**Where a jurisdiction has too few registered institutions for fifty to be meaningful, take the top
ten per cent of every registered institution in that jurisdiction.** The UAE is the case that
prompted this rule. The denominator is every registered institution, so the ten per cent is a real
proportion of a real list rather than ten per cent of whatever we happened to find.

Both the number taken and the size of the list it came from are stored, so the product can say
"the top 12 of 118 registered institutions" rather than an unexplained number.

### Citing the pick

The share is itself a claim, so it carries a source and a year like everything else.

1. Look for the most recent published international student share. Start at 2025.
2. **If 2025 is not published, step back one year and look again. Repeat until data is found.**
3. Record the year found and the publisher, and store both on every school row.
4. Rank by share and take the top fifty, or the top ten per cent where that rule applies.

The guide never says "the top fifty universities". It says the top fifty by international student
share, according to a named publisher, for a named year. If the newest data available is 2023, it
says 2023. **The year is never rounded forward and never left off.**

### Getting to a readable page, in order

1. **The institution's own website and its subpages.** This is always tried first and it is always
   preferred. Check robots.txt before fetching; if it disallows the path, that is the end of that
   path.
2. **If the official site cannot be read, go to the course portals** (MScPortal, BScPortal,
   PhDPortal) and find that institution's own page on the portal, of the form
   `.../school/University-of-East-London`. **That page becomes the source.**
3. **If the portal page cannot be read either, drop that institution and take the next one down the
   list.** The list is ranked by international share, so the next one down is the next best fit, and
   the swap is recorded with the reason.

A dropped institution is recorded as dropped, with which step failed and why. It does not silently
disappear, and the replacement is not passed off as an original choice.

### Saying which of the three it was

A requirement read off the university's own admissions page and the same requirement read off a
portal are not equally good, even when they agree. So every requirement carries **where it was read
from**, in the guide, in words:

- **Official**, meaning the institution's own site.
- **Portal**, meaning a course portal page for that institution, named.

Nothing is hidden and nothing is blocked by this. It costs one short line per requirement, and it
means a reader who wants to double check the second-hand ones can see which those are without
opening anything. A portal citation is still a real citation with a real link and a real date read.
It is just honest about being one step further from the registrar.

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
- for a school: its international student share, the publisher of that figure, the data year, the
  size of the list it was ranked within, and how many were taken from it
- whether the requirement was read from the official site or from a portal, and which portal
- if the institution was dropped: which step failed, and which institution replaced it
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
