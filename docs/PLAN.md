# The plan

Thirteen days to 31 August, 5pm PDT. Written 18 August.

## What must be true to submit at all

The rules make three things mandatory, and all three are already solved from the previous build, so
none of them is a risk:

- Gemini 3.5 or newer. Working, at `location="global"`, which is the trap that costs people an
  evening because every 3.5 model returns 404 in a regional location.
- A Google agent framework. ADK, installed.
- A Google Cloud infrastructure service. Cloud Run, Firestore and Pub/Sub, all already running in a
  project with billing enabled.

Also required: a repo a stranger can spin up, an architecture diagram, and a roughly four minute
video showing it working live.

## Track and prize lane

**Taskmaster**, which the rules describe as a complete workflow rather than a chatbot. That is what
this is.

The realistic prize lane is **Individual/Hobbyist**, two prizes of $10,000, which rewards nothing
about enterprise credibility. **Startup Excellence** is $20,000 and needs an incorporated
organisation with a corporate email, which is worth checking against the US C-Corp because nobody
has looked at that category.

## Order of build

Sequenced so that the thing works end to end early and gets deeper, rather than being wide and
unfinished. Same lesson as last time: reach the visible deliverable as fast as honestly possible.

- [ ] 1. Repo, Cloud Run deploy path, one page that serves
- [ ] 2. The intake form, three lanes
- [ ] 3. Source reader: fetch official pages, extract requirements, attach link and date read
- [ ] 4. The guide, rendered as a document, savable as PDF
- [ ] 5. Document upload and reading, so uploads are matched against requirements
- [ ] 6. Gap analysis: what you have, what is missing, and routes for each missing thing
- [ ] 7. The changelog, seeded from published government change history with real dates
- [ ] 8. Scheduled rounds, so the agent re-reads and records what moved
- [ ] 9. Browser notifications, asked for with permission, fired when a guide changes
- [ ] 10. Architecture diagram, README, video

## Honest risk, stated now rather than on the 30th

**This is a lot for thirteen days.** Three lanes read properly, document reading, PDF rendering,
scheduled watching and web push is more than one build.

If it tightens, the order above is also the order of value. Steps 1 to 6 are the product. Steps 7 to
9 are what makes it an agent that keeps working rather than a generator you run once, and they are
what the Taskmaster track rewards, so they are not decoration either.

**The thing that gets cut first is lane depth, not rigour.** Two lanes done properly beats three
done shallowly, and if it comes to that the third lane stays in the form and says plainly that it is
not covered yet. What does not get cut is the rule that nothing is stated without a source.

## Carried over from ACCESSION

Ported because it is domain independent, not because it exists:

- The GCP project, billing, enabled APIs, Cloud Run deploy path including the build service account
  roles that are not granted by default
- Gemini via Vertex, with the location trap already solved
- Least privilege service accounts and the impersonation module
- **No citation, no claim**, which matters more here than it did there
- Firestore for state, Pub/Sub for work

Not ported: DataHub, the warehouse, the catalog client, the lineage tracing. Those were the previous
domain and they do not follow.
