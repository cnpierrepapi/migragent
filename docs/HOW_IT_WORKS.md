# MIGRAGENT, in plain words

Written before the code, and kept current as it is built. If the build ever contradicts this
document, the document gets fixed rather than ignored.

---

## What it is

You are applying to move country, or to get licensed to work in one. A study permit, a nursing
registration, a skilled work visa.

Today you either pay a consultant around two thousand pounds, or you spend six weekends reading
government websites that contradict each other, and you still get something wrong.

MIGRAGENT asks you about your situation once, reads the official sources itself, and hands you a
document. Not a chat window. A guide you can save as a PDF, print, and take to the bank.

## What it is not

**It is not a chatbot.** There is no conversation. You fill in a short form, you upload what you
already have, and the agent goes away and does work. What comes back is a deliverable.

**It does not give legal advice.** It reports what official sources say, with links, and tells you
what is missing from your file. The decision stays yours.

**It does not predict.** It reports changes that have already happened, with the dates the
government published them. Where those changes point in a direction, it says so, and it says it as
an observation rather than a forecast.

---

## The four things it does

### 1. It takes your situation once

A short form, not an interview. Where you are from, where you are going, what you are applying for,
what you have already done. Three lanes are built properly:

- **Canada study permit**
- **Nursing registration in Canada**
- **UK and EU skilled work visas**

### 2. You upload what you have

Passport, transcript, degree certificate, English test, registration, employment letters. The agent
reads them and works out what is already covered.

This is the part that makes it a real product rather than a checklist generator. A checklist tells
everyone the same thing. This tells you what **you** are missing.

**Where something is missing, it proposes routes rather than stopping.** No English test yet? Here
are the accepted tests, what each costs, how long each takes to book, and which ones this particular
regulator accepts. A second class lower degree? Here are the programmes and bridging routes that
accept one, and the ones that do not. A missing route is still an answer.

### 3. It gives you the guide

Numbered steps in the order you have to do them, because half of these things block each other and
that is where people lose months. For each step: what it is, whether your uploads already satisfy
it, what it costs, how long it takes, and what it depends on.

**Every requirement carries the link it came from and the date it was read.** If the agent cannot
find an official source for something, it does not state it. It goes into a section at the back
called open questions, which is the honest place for it.

That rule is carried over from the last build and it matters more here. A confidently invented
requirement in this domain costs somebody their savings and half a year.

### 4. It keeps watching, and tells you when something moves

The rules change. Someone who got a guide in March and applies in September is working from a
document that has quietly gone wrong.

So the agent makes rounds. It re-reads the sources on a schedule, and when a requirement changes it
records the change, with both versions and both dates.

**The browser asks your permission to send notifications.** If you allow it, you get told when
something in your guide moves, rather than finding out at the bank.

### The change line, and why it is built this way

Alongside your guide there is a record of how the rules have moved over time. Real changes, real
published dates, real sources. Canada's proof of funds requirement for a study permit has moved more
than once. Provincial attestation letters did not exist and then did.

From that record the guide can say something genuinely useful: this lane has been getting stricter,
and here are the four changes in the last two years that say so.

**One thing we are deliberately not doing.** The other way to demonstrate this was to backdate an
agent run to before a policy change, so it looks like the agent was watching at the time. That means
writing down that something happened on a day it did not happen. Every claim this product makes
depends on its records being true, so we do not begin by faking one. The changelog is seeded from
the government's own published history, with their dates, and the agent's own runs carry the dates
they actually ran.

---

## Why a judge should care

The hackathon's own advice is to solve a real, specific problem you actually have, and to show the
agent doing something rather than talking.

This is a problem in this house right now. Two applications are sitting blocked on exactly this.

And the agent is visibly not talking. It reads a form, opens documents, goes out to several official
sources, and produces a file you can open. The demo is: fill it in, watch it work, open the PDF.

---

---

## What it looks like, and what it costs

### The look

Two faces on purpose. Light is bright and youthful, because starting an application is a hopeful
thing. Dark is elite and mature, because the document it hands back has to survive being read across
a desk by a bank officer. Most of the difference is not colour, it is geometry: dark is tighter,
flatter and quieter.

The whole brand pack is in `docs/BRAND.md`, and the files it describes are in `web/brand/`. Every
contrast ratio quoted there was measured by `tools/contrast.py` before it was written down, because
a palette that says it is accessible without a measurement is the same untested claim this project
keeps promising not to make.

One animation earns its place: the run itself, one line per source as it lands, with the address and
the moment it was read, and a counter showing the real number. A product whose pitch is that it does
not invent things cannot have an interface that performs work it is not doing.

### What it costs

The first agent run is free, with the full guide and the PDF.

After that it is $14 a month for reruns and the daily digest, or $105 once per case for the done
for you tier.

The detail is in `docs/BRAND.md`, including two things that are not settled yet: the fact that the number of watched sources shown on
the page is always the live count from the registry rather than an aspiration, and where the line
sits between preparing somebody's documents and representing them, which is a regulated activity in
Canada and needs a licensed third party.

**None of this is in Builds 1 to 4.** Payment is not part of the hackathon entry and no billing code
goes in before 31 August. The design carries the prices so the interface is right. The plumbing
waits.

---

## How it actually feels to use, in three stages

Set on 18 August 2026. This replaces "a short form and then a document" with something with more
shape to it, and it is written here before any of it is built.

### Stage one. You tell it about yourself, and you watch a number go up

You fill in your details, and you upload the documents you already have.

**Uploading is not a gate.** You can get a guide with nothing uploaded at all. It will just be a
more general guide, and the product should say so rather than pretending otherwise.

**There is a readiness score on screen, and it climbs as you add things.** When it crosses the
threshold the confetti fires and the **GO** button lights up.

**The documents are listed by how much they are worth**, because they are genuinely not worth the
same. A passport moves the number a lot. A high school transcript moves it a little. That ordering
is not a gamification trick, it is the truth about which documents actually unlock requirements, and
showing it saves somebody hunting for a certificate that was never going to matter much.

**The score has to be real, and this is the part that can go wrong.** A number that climbs because
you uploaded *something* is a progress bar pretending to be an assessment, and this product cannot
afford one of those. So the score is computed from actual coverage: how many of the requirements
we have actually extracted for your lane are addressed by what you have actually uploaded. If the
lane has forty requirements and your uploads speak to twelve of them, the number says so. When you
tap the score it opens and shows which requirements each document covered.

The confetti is then honest, because it is celebrating a real threshold rather than the act of
clicking. Under `prefers-reduced-motion` it does not fire.

### Stage two. The agent goes and builds your guide

It searches the corpus and the registry, and matches what it finds against your profile: your
jurisdiction, your lane, your documents, your gaps.

This is the stage where the run animation lives. One line per source as it lands, with the address
and the moment it was read, and a counter showing the real number.

### Stage three. A guide, a form to fill in, and a board of work

Two things come back rather than one.

**The guide**, as before. Ordered steps, dependencies, cost, duration, the source and the date read
on every line, and open questions at the back.

**A fillable form**, generated for your case. Filling it in gives the agent the context that a
generic intake could never ask for, because by now it knows which lane you are in and what is
missing from your file. This is the second pass, and it is where a general guide becomes yours.

**Then your dashboard fills up with a board of tasks**, in columns you can move things between.

**The agent does the parts it can do.** It writes the cover letter for a specific job. It builds the
CV for a specific school or role, per application rather than one CV for everything. What lands on
your board is a piece of work that is already done, waiting for you to check it and send it.

**You submit, and you come back and tick it off.** The agent does not claim to have submitted
anything on your behalf, and it does not tick anything off for you. The board reflects what has
really happened.

**And it keeps going**, because the corpus is being re-read on a schedule. When something moves that
touches your case, new tasks appear on the board and stale ones are marked, rather than you holding
a document that quietly went wrong.

### What has to stay true in all of this

The board is a record of real state. A task is not marked done because an agent thinks it went well,
and a drafted cover letter is labelled a draft until a person has read it. Anything the agent
produces that has not been checked by you says so on its face.

### Where these land in the build order

Stage one and stage three are a lot more product than the four builds currently describe, so this is
the honest mapping rather than a promise that all of it arrives at once.

| Piece | Where it belongs |
| --- | --- |
| Details form, guide, PDF | Build 1, unchanged |
| Uploads, the readiness score, confetti and GO | Build 2, since the score depends on reading documents |
| Corpus search and profile matching | Build 1 for one lane, widened in Build 3 |
| The generated fillable form | Build 2 |
| The kanban board | new, and it sits after Build 4 |
| Cover letters and per-application CVs | new, and the largest single piece of work here |
| Board updated from the watcher | Build 3 and Build 4 together |

**The board and the written applications are not in the hackathon entry.** They are the product, and
they are the reason somebody pays $14 a month, but the entry is due on 31 August and the entry is
the guide, the documents and the watcher working properly. Saying that now is cheaper than
discovering it on the 30th.

## Build log

Started 18 August 2026. Nothing here is claimed as working until it has been checked.
