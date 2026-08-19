# MIGRAGENT

You are applying to move country, or to get licensed to work in one. MIGRAGENT asks two questions,
takes whatever paperwork you already have, reads the official sources itself, and gives you a guide
you can save as a PDF.

It is not a chatbot. There is no conversation to steer and no prompt box. You make two choices, drop
your files, and an agent goes away and does the work while you watch each step finish.

Live: https://migragent-158351874494.us-central1.run.app

## What it will not do

**Nothing is stated without a source.** Every requirement in the guide carries the official page it
came from and the date that page was read. The citation is built from the fetch and never passes
through the model, so a link cannot be invented.

**Every requirement carries a verbatim quote, checked against the page text before the requirement is
allowed to exist.** A real sentence with one number changed is rejected. Two real fragments stitched
together are rejected. Where nothing can be quoted, the requirement is not stated: it goes to open
questions at the back of the guide.

**No run is backdated and no count is rounded up.** The number of sources shown is the number in the
registry today. The screen you watch while the agent works has no sleep in it and no artificial
pacing; each line appears when that step really finished, carrying the count it really produced.

## What is covered

The registry holds 1,046 sources across seven jurisdictions and two lanes each, work and study:
United Kingdom, United States, Canada, Australia, France, Spain, United Arab Emirates. Four are
recorded as blocked rather than quietly dropped. US study and work, because those hosts refuse to
serve their robots.txt to anybody, so we cannot learn their rules and do not crawl them. AU study and
work, because that host serves its robots.txt to a generic client and refuses it to one that says who
it is. Neither is the same as being disallowed, and the registry says which it is.

Extraction runs lane by lane. Two lanes are deep today, with 708 requirements in the corpus: Canada
study, 568, and UK study, 140. The intake screen greys out what it cannot serve and says why, rather
than offering a lane it would answer thinly.

## Running it

You need a Google Cloud project with Firestore, Cloud Run and Vertex AI enabled, and the four service
accounts created by `tools/grant_roles.sh`.

```
pip install -r requirements.txt
export GOOGLE_CLOUD_PROJECT=<your project>
python -m flask --app migragent.app run
```

Crawling and extraction are separate from the web application on purpose, and are run as tools. They
need a browser, which the deployed container deliberately does not carry:

```
pip install playwright && playwright install chromium

python -m tools.seed_registry          # fill the source registry
python -m tools.expand_registry        # walk out from the entry pages
python -m tools.extract_lane CA study  # pages to requirements
python -m tools.build_guide CA study   # guide to PDF
python -m tools.test_isolation         # prove the workers cannot reach each other
```

## Deploying

Push to `main` and the running service becomes that commit. `.github/workflows/deploy.yml` builds and
moves the Cloud Run revision, then fails the job unless the new revision answers on `/health`.

There is no service account key in the repository or in its GitHub secrets. GitHub proves who it is
with a short lived OIDC token, Google checks the token names this repository, and the credential it
gets back lasts minutes. The deploy identity can build an image and move a revision; it cannot read
Firestore, so it cannot see a case or a document.

## Pre-existing code

`migragent/identity.py` and `migragent/config.py` were written on 17 August 2026 for an earlier
project of mine and carried across. `docs/INHERITED.md` records exactly what came with them and which
of the gotchas they document have since turned out to be stale. Everything else was written for this
submission.

## Reading further

`docs/HOW_IT_WORKS.md` is the whole thing in plain words. `docs/PLAN.md` is what is built and what is
not. `docs/RULES.md` is the standing rules the code has to keep. `docs/DECISIONS.md` records the
choices, including one that turned out to be over-investment. `docs/DEFECTS.md` is every defect found
so far, what caused it and how it was proved fixed.
