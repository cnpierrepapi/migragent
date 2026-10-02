## What MIGRAGENT is now

An AI reporter. It reads official immigration pages every morning, works out what changed, and writes it up on the wire. You read it. That's the whole transaction.

There are no accounts. Nothing to upload. No form asks for your name, your passport or your plans. Reading an article tells MIGRAGENT nothing about you that a newspaper's website wouldn't know.

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

## How the writing gets done

The agent uses Gemini, Google's model, in two ways.

Most mornings it goes through Orbio, an AI gateway paid for by $MIGRA's trading fees. Orbio passes the request on through OpenRouter to Google. When that balance runs out it goes to Vertex AI, inside the same Google Cloud project as everything else.

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
| No accounts, no uploads, no forms that ask about you | true; the routes that took them were removed on 2 October 2026 |
| No cookies for readers, no analytics | true in code; the only cookie is the editor's desk session |
| Request logs with IP addresses are kept by Google Cloud | true; this is the host's standard logging, not ours to turn off |
| Only public page text goes to Orbio | true; `tools/test_orbio_route.py` checks it |
| Old cases are deleted on schedule, the last by 31 October 2026 | true; the sweep still runs, and `tools/test_retention.py` covers it |
| An old case can be deleted now with the button below | true, for a browser that still holds its cookie |
| Every article can be checked against the page it came from | true for anyone with the link, which shows today's page; the stored copies are kept privately |
