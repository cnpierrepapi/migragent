## What MIGRAGENT is now

An AI reporter. It reads official immigration pages every morning, works out what changed, and writes it up on the wire. You read it. That's the whole transaction.

There are no accounts and nothing to upload. Reading an article tells MIGRAGENT nothing about you that a newspaper's website wouldn't know.

Two forms exist, and you only fill them in if you want to. One signs you up for alerts. The other reserves a place on the Desk, the paid version for agents and advisers. Both are below.

Until 2 October 2026 it also took people's cases: you could upload documents and get a guide. That part is gone. What's left of it is covered at the bottom of this page.

## What it keeps

Public things, mostly.

- The official pages it reads, stored exactly as they arrived, so every article can be checked against the version it was written from. These are government pages. Nothing personal is in them.
- What it read from those pages: requirements, each with the sentence it came from.
- What changed between two reads of a page, and the articles written about it, each with its report.
- A log of every morning's reading: pages fetched, what moved, what it cost.

None of that is about you.

## What happens when you visit

The site sets no cookies for readers and runs no analytics. There are no ad trackers and no tracking pixels.

Two ordinary things still happen, and they aren't ours to switch off. The site runs on Google Cloud Run, which logs each request, including the IP address it came from, the way any web host does. And the fonts load from Google Fonts, so your browser asks Google for them. If you'd rather not touch Google at all, this site isn't the place.

## If you sign up for alerts

We keep your email, what describes you (agent, adviser, student, and so on), the countries you picked, the page you signed up on, and when. That's it. It's used to send you rule changes for those countries, and nothing else. It isn't sold or shared.

No alert has gone out yet. When they start, every one will have a link that deletes you from the list in one click. The link on the page right after you sign up does the same thing today.

## If you reserve a place on the Desk

We keep your email, the name you gave, the plan you picked, and the Paystack reference for your deposit. Your card never touches MIGRAGENT. Paystack takes the payment on its own page, and we ask Paystack afterwards whether it went through. The deposit is refunded in full if you ask, by email to admin@onenept.com.

## Links to other companies

Some guides carry a box for something you'd need next, like an English test or a way to move money. Those are affiliate links, and each box says so. Clicking one takes you to that company's site, under their privacy policy, and they may pay us a commission. We don't pass them anything about you.

## How the writing gets done

The agent uses Gemini, Google's model. Since 2 October 2026 it runs through Vertex AI, inside the same Google Cloud project as everything else.

Before that, and again whenever $MIGRA's credit is switched back on, it can go through Orbio, an AI gateway paid for by the token's trading fees. Orbio passes the request on through OpenRouter to Google.

What travels down either road is the text of public government pages and the agent's notes on them. Nothing about a reader is ever in it, because the site holds nothing about a reader to send. `tools/test_orbio_route.py` fails if any code that ever handled personal data is pointed at Orbio.

## The desk

One person, the editor, can sign in to a private desk to file things the crawl can't reach: a PDF, a page behind a login, an announcement. What gets filed there is official information, kept with the article it became. The desk signs in with a key held in Google Secret Manager, on a cookie that only the editor's browser ever gets.

## If you used the old case product

You were told your data would be kept for 30 days after you last touched your case, then deleted. That still happens. The sweep that deletes old cases keeps running, and the last of them goes by 31 October 2026.

On 2 October there were five cases left, holding only a choice of study or work. No documents, CVs, profiles, alerts or wallet links remained, and $MIGRA payments never went live, so no payment records exist.

If your browser still has the case cookie, you can delete yours now with the button below. If it doesn't, the sweep gets to it anyway.

## What is true, and how you'd know

| Claim | Status |
| --- | --- |
| No accounts, no uploads | true; the routes that took them were removed on 2 October 2026 |
| The alerts signup keeps an email, a role and countries, and nothing else | true in code, `migragent/signup.py` |
| One click deletes you from the alerts list | true; the link is shown right after signup and will be in every alert |
| Card details never reach MIGRAGENT | true; Paystack's hosted checkout takes the payment |
| A deposit is only marked paid after Paystack confirms it, for the right amount, in naira | true in code, `migragent/app.py` |
| Affiliate links are labelled | true on every box |
| No cookies for readers, no analytics | true in code; the only cookie is the editor's sign-in session |
| Request logs with IP addresses are kept by Google Cloud | true; this is the host's standard logging, not ours to turn off |
| Only public page text goes to Orbio | true; `tools/test_orbio_route.py` checks it |
| Old cases are deleted on schedule, the last by 31 October 2026 | true; the sweep still runs, and `tools/test_retention.py` covers it |
| An old case can be deleted now with the button below | true, for a browser that still holds its cookie |
| Every article can be checked against the page it came from | true for anyone with the link, which shows today's page; the stored copies are kept privately |
