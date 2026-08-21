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

## The one thing that is kept: a profile picture

Everything above is about documents, and for documents the promise is unchanged: read in memory,
fields survive, file does not.

A profile picture is different, and pretending otherwise would be the dishonest option. Its whole
purpose is to be kept and shown back to you. So:

- **It is resized to 256 pixels square in your own browser before it is sent.** The original file is
  never uploaded. The full resolution photograph does not reach this server, does not appear in a
  request log, and never has to be trusted to a deletion path.
- **What is stored is that thumbnail**, in your case's own row, as a data URI. No bucket, no second
  storage identity, no signed URLs for what is a thumbnail.
- **It is checked before it is stored.** The prefix, the media type, the decoded size and the file's
  own magic number all have to agree. The browser's good behaviour is a convenience, not a control:
  anybody can post to that endpoint.
- **SVG is refused**, because it can carry script and this is the one field rendered back to
  whoever looks at the page.
- **It is deleted with the case**, on the same path as everything else, and `tools/test_delete.py`
  counts it before and after like every other collection.

A name and an optional contact address are stored the same way and go the same way. None of it is
verified, none of it is required, and nothing is sent anywhere.

So the precise version of the promise, which is what the pages now say:

> Documents you upload are never kept. A profile picture is, because it exists to be shown to you,
> and it is deleted with everything else.

---

## The watch

Turning the watch on stores one more row: which country and which route this case is about, when
the watch started, and when it last ran. It is off unless you turn it on, and off again the moment
you turn it off.

What it produces are alerts, and each one holds a headline, the date the thing was observed, and a
link to the official page it was read from. **An alert says what somebody is applying for, and
where.** That makes them among the more sensitive rows here, not less, and they are deleted with
the case like everything else.

Nothing is sent anywhere. There is no mail sender in this project and none is pretended: alerts are
written to a collection and read on `/alerts` while you are signed in to your own case. If a sender
is ever added, the address it needs will be asked for at that point, and this section will say so.

---

## Deleting it yourself

There is a delete path and it deletes. It removes the case, the document fields, the coverage
result, the guide built from it, the CV claims, the fit scores, the board, the watch and every
alert, and it reports what it removed so the person can see the numbers rather than a
reassurance.

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
| 30 day retention with a restarting countdown | true; the sweeper runs and is tested |
| Delete removes everything and reports counts | built, and tested by counting rows |
| The watch is off until you turn it on | true in code; there is no default-on path |
| Alerts go when the case goes | true; `tools/test_delete.py` counts them before and after |
| Nothing is emailed or sent off the platform | true; no sender exists |
| Documents are never kept | true in code, unchanged |
| A profile picture is kept, resized in the browser first | true in code |
| The picture is deleted with the case | true; counted before and after in the delete test |
| Encrypted at rest and in transit, Google managed keys | true, by default, nothing configured |

**The sweeper now exists**, and `tools/test_retention.py` proves it in the direction that matters.
Any sweeper deletes expired cases; the test also writes a case that has NOT expired and fails if the
sweep touches it, because a sweeper that takes everything would pass the easy half of that test.

It runs on a schedule through Cloud Scheduler against an authenticated endpoint. Between runs, a
case past its date still exists, so the honest wording is that a case is deleted within a day of its
expiry rather than at the instant of it.
