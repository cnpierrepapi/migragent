# Standing rules for MIGRAGENT

These are not preferences. They are the things that make the product worth anything, and every one
of them came from a real failure, either in this build or the one before it.

If code and this file disagree, the code is wrong.

---

## Evidence

1. **The citation comes from the fetch, never from the model.** The URL and the date read are
   captured by the fetcher and attached to the requirement. A model is never asked where something
   came from, so a source cannot be invented.
2. **No source, no claim.** A requirement with no official source is not stated. It goes to open
   questions at the back of the guide.
3. **Never write a claim before the test that proves it.** Not in a document, not in a comment, not
   in a UI string. This is D1 and D2 in the defect log and it is the failure that came across from
   the last build.
4. **Never backdate a run and never fake a record.** An agent run carries the date it actually ran.
   The change line is seeded from published government history with their dates.
5. **The real number, never a rounder one.** Source counts, school counts and coverage scores are
   read live. On the day it is nine it says nine.
6. **Extract from the original language.** Keep the original sentence verbatim beside the
   translation. Extracting from a translation lets a translation error become an invented
   requirement with an official link next to it.
7. **A derived ranking carries its publisher and its data year.** Start at 2025 and step back a year
   at a time until real data exists. The year is never rounded forward and never omitted.
8. **Every requirement says where it was read from**, Official or Portal.
9. **A lead is how we found it. A source is what we read.** Two fields, never collapsed.
10. **robots.txt is a gate, not advice.** No fetching anyway, no changing the user agent to get
    around it.
11. **Nothing silently disappears.** An unreadable source is recorded with the reason. A dropped
    institution is recorded with the step that failed and the one that replaced it.
12. **The readiness score is computed from real coverage**, meaning how many extracted requirements
    the uploads actually address. Never from the act of uploading. Tapping it shows which document
    covered which requirement.
13. **Nothing is ticked off on the user's behalf.** Anything an agent produced that a person has not
    checked is labelled a draft on its face.
14. **Hash first.** A byte-identical page stops there. No model call, no cost.

## Interface

15. **Light is bright and youthful, dark is elite and mature**, and the difference is geometry
    before colour: radius, rule weight, letter spacing, display weight, density.
16. **Contrast is measured, not judged.** `tools/contrast.py` runs before any ratio is written down.
17. **The accent colour never carries text.** It measures 1.52 against paper. It is a highlighter.
18. **Two animations exist:** the run, and the confetti at a real threshold. Both stop under
    `prefers-reduced-motion`. Nothing else animates work that is not happening.
19. **Photography:** no government crest or seal, no readable document, no recognisable face, no
    aeroplanes, globes, pins or suitcases. Every generated image is looked at before it is used.
20. **Fonts are self-hosted.** The PDF renderer cannot depend on a font CDN.

## Words

21. Second person, present tense, short sentences, exact numbers.
22. **No em dashes in shipped copy or code.**
23. Never: seamless, empower, unlock, revolutionise, effortless, journey, AI powered. Never a
    guarantee of an outcome. Never the words legal advice.
24. Plain words. Any term a reader would have to look up gets explained where it is used.

## Engineering

25. **ADK sits on the researcher and nowhere else.** Fetching, hashing, diffing and rendering are
    plain code on purpose.
26. **Gemini model calls pin to `location="global"`.** Every 3.5 model returns 404 in `us-central1`.
27. **Images use `gemini-2.5-flash-image`** on the same project. Every Imagen endpoint 404s here.
28. **The registry is data, not code.** Source 400 is a row, not a deploy.
29. **Each worker runs as its own service account** with only the permissions its job needs.
30. **No Firestore composite indexes.** Sort in Python.
31. **`/health`, never `/healthz`.** Something in front of Cloud Run claims that path.
32. **State the ambient identity in an environment variable.** Detecting it from the credential
    hangs on Cloud Run.
33. **Resolve `gcloud` with `shutil.which`** on Windows. It is a `.cmd` and bare `subprocess` cannot
    launch it.
34. **Verify file copies with a checksum.**

## Working

35. **Commit every finished task without asking. Halt before deploying.**
36. **Every bug and its fix goes in `docs/DEFECTS.md` as it happens**, with how it was found.
37. **No Claude traces in the repo.** No co-author trailer, no mention, commits read as a person
    wrote them.
38. **The docs get fixed rather than ignored.** If the build contradicts a document, the document is
    wrong and gets corrected in the same commit.
