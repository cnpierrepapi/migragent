# MIGRAGENT, in plain words

Kept current as the thing gets built. If the code and this file disagree, this file is wrong and
gets fixed.

## What it is

You want to study or work in another country. Right now you either pay a consultant a couple of
thousand pounds, or you spend six weekends on government websites that contradict each other and
still get something wrong.

MIGRAGENT reads those websites for you. Every day. It hands you the steps, the documents, the
money and the deadlines for your case, and every line carries the sentence it came from.

Then it keeps going after you close the tab. That second part is the whole product. A guide is a
photograph. This is a person who keeps watching.

## The order is backwards on purpose

Every version of this before August asked you to pick a country first. That is the wrong question
and we asked it for months.

Think about it. Somebody who does not already know Canada is short of welders cannot choose Canada
for being short of welders. Asking them to pick makes them do the exact research the product
exists to do. They pick wrong, or they pick the country their cousin went to, and everything after
that is built on a guess.

So now it goes:

1. Say what you want. Study, work, or both.
2. Upload what you have. A CV, or transcripts. A phone photo is fine.
3. The countries come out of your documents.

Step three is the interesting one. A work country shows up only when its own published shortage
list matches something your CV says, and the card tells you which sentence did it. A study country
shows up only when a school on its official register teaches your level in your subject.

Nothing else appears. If you would not qualify, you never see it, because showing it costs you
either a wasted month or a refusal with a fee attached.

## What it is not

Not a chatbot. There is no conversation and there is no box to type into. You tap twice, drop a
file, and it goes away and works.

Not legal advice. It reports what official pages say, with links and dates, and tells you what is
missing from your file. The decision stays yours.

Not a search engine. You never search for anything. There is no filter, no browse, no results
page. What you see is what your own documents opened.

## The one rule everything else hangs off

Nothing is stated without a sentence behind it.

A requirement stores the words from the government page. A course stores the words from the school
page. A shortage occupation stores the line from the list. Each one gets checked against that
page's own text before the row is kept, and anything that fails is thrown away rather than shown
with a caveat.

Across 3,686 courses pulled off school websites, 29 got dropped for a quote that was not really
there. That is the check doing its job.

This is also why the gaps stay visible. Only 146 of 3,990 courses carry a fee, because most
universities keep tuition behind a calculator. We could guess. We do not. The course still shows,
with "what does this cost for an international student?" pointed at that school's admissions
office.

A gap you can act on beats a number you cannot trust.

## What you get, free

Every country your documents qualify you for. Every course we have read at your level and in your
subject. The guide, with its sources. Your CV laid out three ways, Canadian, British and Europass,
because those are three different documents and employers expect their own.

And a question with a link, everywhere a school did not publish something.

## What seven dollars buys

Timing. Start dates, application windows, and the alert that fires when a job you qualify for gets
posted.

Not access. The line is deliberately drawn at when things happen rather than what exists, because
any other line makes the free product dishonest. Hiding a country you qualify for so you will pay
to see it would be lying by omission with a price on it.

Billing is not built. The page says so rather than showing a checkout that goes nowhere.

## How it stays current

Four jobs, every morning, in this order.

The retention sweep runs at 03:17 and deletes cases past their thirty days. The watch round runs
at 04:40, re-reads every government page, and diffs it against yesterday. Job listings come in at
05:00. The digest runs at 05:20 and tells each watching case what moved.

Order matters. Read the pages, ask the boards, then tell people. Flip the last two and the digest
reports on yesterday's jobs.

The watch round is careful about crying wolf. On the first real run, 95 pages out of 143 came back
with a different digest and not one word of text had changed. Timestamps, nonces, edge caches. So
a change is only a change when the words move, because a watcher that fires every day teaches you
to ignore it, and then you ignore the one that mattered.

## Where it works today

Study works for Canada and the United Kingdom. 3,990 courses across 241 schools.

Work works for Canada. 2,042 live postings, matched against what your CV actually says.

Six more countries have a visa guide and nothing else yet. The UK's job board will not say whether
it allows crawlers, so we do not read it. Australia's says no outright. Both of those are closed
doors rather than a to-do list, and `docs/SOURCES.md` records what was checked and when.

## Your documents

The file is never kept. It gets read in memory and thrown away, and what survives is the fields it
said, each with its quote.

One exception, and it is deliberate. A profile picture is kept, because a picture exists to be
shown back to you. Your browser shrinks it to 256 pixels before it sends anything, so the full
photo never reaches us at all. It goes when the case goes.

Everything goes when the case goes. Thirty days after you last touch it, or the moment you press
delete, and the delete reports what it removed instead of just saying "done".
