# PASSAGE, in plain words

Written before the code, and kept current as it is built. If the build ever contradicts this
document, the document gets fixed rather than ignored.

---

## What it is

You are applying to move country, or to get licensed to work in one. A study permit, a nursing
registration, a skilled work visa.

Today you either pay a consultant around two thousand pounds, or you spend six weekends reading
government websites that contradict each other, and you still get something wrong.

PASSAGE asks you about your situation once, reads the official sources itself, and hands you a
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

## Build log

Started 18 August 2026. Nothing here is claimed as working until it has been checked.
