# Standing rules for MIGRAGENT

Not preferences. These are the things that make the product worth anything, and every one came from
a real failure, in this build or the one before it.

If code and this file disagree, the code is wrong.

## The shape of the product

First because it governs everything below it. Numbered last because the code references the numbers
and renumbering would break those references.

39. There is no search. Anywhere. Ever.
    - The product shows you things because of what you uploaded and what you filled in. Nothing
      else.
    - No search box, no query field, no free text prompt, no browse-everything list, no filters
      over content you haven't been matched to, no chat. A user never types a question at this
      product.
    - The only two ways in are a call to action and a drag and drop. A button that says what
      happens when you press it, and a place to drop a file.
    - Content a user hasn't earned through their own case doesn't appear to them. A listing, a
      change, a requirement or a route reaches somebody because their case matched it, and it
      arrives with the reason it reached them.
    - This is what makes it an agent instead of a website with a database behind it. A search box
      hands the work back to the person who came here to have it taken off them. The moment one
      exists the product is a directory, and every claim in it is something the user went looking
      for rather than something we stand behind.
    - Public marketing pages aren't the product. If a browsable country page ever gets published
      for people who haven't signed up, it lives outside the application and is written as
      marketing, not as somebody's guide.

## Evidence

1. The citation comes from the fetch, never from the model. The fetcher captures the URL and the
   date read and attaches them to the requirement. A model is never asked where something came
   from, so a source can't be invented.
2. No source, no claim. A requirement with no official source isn't stated. It goes to open
   questions at the back of the guide.
3. Never write a claim before the test that proves it. Not in a document, not in a comment, not in
   a UI string. This is D1 and D2 in the defect log, and it's the failure that came across from the
   last build.
4. Never backdate a run and never fake a record. An agent run carries the date it actually ran. The
   change line is seeded from published government history with their dates.
5. The real number, never a rounder one. Source counts, school counts and coverage scores are read
   live. On the day it's nine it says nine.
6. Extract from the original language. Keep the original sentence word for word beside the
   translation. Extracting from a translation lets a translation error become an invented
   requirement with an official link next to it.
7. A derived ranking carries its publisher and its data year. Start at 2025 and step back a year at
   a time until real data exists. The year is never rounded forward and never left off.
8. Every requirement says where it was read from, Official or Portal.
9. A lead is how we found it. A source is what we read. Two fields, never collapsed.
10. robots.txt is a gate, not advice. No fetching anyway, no changing the user agent to get around
    it.
11. Nothing silently disappears. An unreadable source is recorded with the reason. A dropped
    institution is recorded with the step that failed and the one that replaced it.
12. The readiness score is computed from real coverage, meaning how many extracted requirements the
    uploads actually address. Never from the act of uploading. Tapping it shows which document
    covered which requirement.
13. Nothing is ticked off on the user's behalf. Anything an agent produced that a person hasn't
    checked is labelled a draft on its face.
14. Hash first. A byte-identical page stops there. No model call, no cost.

## Interface

15. Light is bright and youthful, dark is elite and mature, and the difference is geometry before
    colour: radius, rule weight, letter spacing, display weight, density.
16. Contrast is measured, not judged. `tools/contrast.py` runs before any ratio is written down.
17. The accent colour never carries text. It measures 1.52 against paper. It's a highlighter.
18. Two animations exist: the run, and the confetti at a real threshold. Both stop under
    `prefers-reduced-motion`. Nothing else animates work that isn't happening.
19. Photography: no government crest or seal, no readable document, no recognisable face, no
    aeroplanes, globes, pins or suitcases. Every generated image is looked at before it's used.
20. Fonts are self-hosted. The PDF renderer can't depend on a font CDN.

## Words

21. Second person, present tense, short sentences, exact numbers.
22. No em dashes in shipped copy or code.
23. Never: seamless, empower, unlock, revolutionise, effortless, journey, AI powered. Never a
    guarantee of an outcome. Never the words legal advice.
24. Plain words. Any term a reader would have to look up gets explained where it's used.

## Engineering

25. ADK sits on four agents and nowhere else: the researcher, the scout, the extractor, the
    coverage matcher. Each one is a place where the model decides across several steps what to do
    next. Fetching, hashing, the quote check, diffing, the lane check and rendering are plain code
    on purpose, because they're rules rather than judgment, and a rule an agent can skip is not a
    rule. Decision 12 has the full split.
26. Gemini model calls pin to `location="global"`. Every 3.5 model returns 404 in `us-central1`.
27. Images use `gemini-2.5-flash-image` on the same project. Every Imagen endpoint 404s here.
28. The registry is data, not code. Source 400 is a row, not a deploy.
29. Each worker runs as its own service account with only the permissions its job needs.
30. No Firestore composite indexes. Sort in Python.
31. `/health`, never `/healthz`. Something in front of Cloud Run claims that path.
32. State the ambient identity in an environment variable. Detecting it from the credential hangs
    on Cloud Run.
33. Resolve `gcloud` with `shutil.which` on Windows. It's a `.cmd` and bare `subprocess` can't
    launch it.
34. Verify file copies with a checksum.

## Working

35. Commit every finished task without asking. Halt before deploying.
36. Every bug and its fix goes in `docs/DEFECTS.md` as it happens, with how it was found.
37. No tooling traces in the repo. No co-author trailers, no assistant named anywhere, commits read
    as a person wrote them.
38. The docs get fixed rather than ignored. If the build contradicts a document, the document is
    wrong and gets corrected in the same commit.

## The agent

40. The rules live in the tools, not in the prompt. An agent may choose what to read. It may not
    fetch, and it may not record a requirement, except by asking a tool that applies the robots
    gate and the quote check first. A rule an agent can skip is not a rule.
41. Every model call goes through `migragent/model.py`, including an agent's. A framework that
    brings its own client gets an adapter, not an exemption. Checked by `tools/test_agent.py`.
42. Budgets are caps in code, not requests in an instruction. Pages read and model turns are
    counted by the loop that runs the agent.
43. What an agent was refused is reported next to what it kept. A session that had nine of ten
    quotes rejected has said something about itself, and swallowing it hides the one thing worth
    knowing.
