# What happens to the documents you upload

People upload passports here. This document is written before the upload feature ships rather than
after, and it describes what the code does, not what we intend it to do. Anything below that is not
true yet says so.

---

## The short version

**The file is not kept.** It is held in memory long enough to be read, and then it is gone. What
persists is the fields that were read from it, not the document.

Nobody needs a copy of your passport in a bucket to tell you that it expires before your course
ends. They need the expiry date. So that is what is stored.

---

## What is stored, exactly

For each document you upload:

- the kind of document it was taken to be, for example `passport`
- the filename you uploaded it under
- the moment it was read
- the fields read from it, each with the quote from the document that supports it
- whether each field was verified against a text layer, or could not be
- anything the model claimed that was dropped for having no findable quote

**What is never stored:** the file itself, the bytes, an image, a thumbnail, or any copy in Cloud
Storage. The snapshot bucket holds government pages and nothing a person uploaded.

---

## Why fields and not files

A stored passport scan is a liability that grows every day it exists and helps nobody after the
first minute. A stored expiry date does the same job for the person and is worth nothing to anybody
else.

This is also the reason the reader is asked for quotes. Storing the sentence a field came from means
a person can see why we think their passport expires in 2029, without us keeping the page it says
so on.

---

## Retention

**A case is deleted 30 days after it was last touched.** Not archived, not anonymised, deleted.

Thirty days is chosen to cover the realistic gap between starting an application and coming back to
finish it, and not longer. There is no business reason to hold somebody's document fields for a year
and no honest way to describe doing so as being for their benefit.

**The countdown restarts when you use it.** A case you are actively working on is not deleted out
from under you.

---

## Deleting it yourself

There is a delete path and it deletes. It removes the case, the document fields, the coverage
result and the guide built from it, and it reports what it removed so the person can see the numbers
rather than a reassurance.

**A delete that leaves an orphan somewhere is a broken delete**, so the test for it counts the rows
before and after in every collection a case touches, and it fails if anything survives.

---

## Encryption

Everything in Firestore and Cloud Storage is encrypted at rest by Google, with Google managed keys,
and in transit over TLS. No customer managed key is configured, and this document does not claim one
is.

The uploaded file travels over TLS to Cloud Run, is read in memory, and is never written to disk by
this application.

---

## Who inside the system can see what

- `migragent-web` writes case data and document fields. It cannot call a model and cannot start a
  crawl round.
- `migragent-researcher` reads government pages and cannot read the case collections.
- The snapshot bucket contains government pages only. The researcher can add to it and cannot read,
  overwrite, delete or list what is there, which was measured and is in `tools/test_isolation.py`.

---

## What this is not

It is not a claim of compliance with any particular regime. It is a description of what the code
does. If somebody needs a GDPR representative, a DPA or a records of processing document, those are
real pieces of work and none of them exists yet.

---

## Status of each claim above

| Claim | State |
| --- | --- |
| The file is never written to disk or a bucket | true in code |
| Only fields are stored | true in code |
| 30 day retention with a restarting countdown | field is written; the sweeper is not built yet |
| Delete removes everything and reports counts | built, and tested by counting rows |
| Encrypted at rest and in transit, Google managed keys | true, by default, nothing configured |

**The retention sweeper is the outstanding one.** Until it runs on a schedule, the expiry is a date
stored on the case and nothing enforces it. That is stated here rather than glossed, because a
retention promise nothing enforces is exactly the sort of claim `docs/RULES.md` rule 3 exists to
stop.
