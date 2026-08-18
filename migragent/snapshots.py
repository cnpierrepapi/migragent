"""Keeping the page behind the citation.

"Read on 18 August 2026" means nothing if the page it refers to is gone or has
since changed. So every fetch that succeeds is stored exactly as it arrived,
and the guide's date points at bytes somebody can still open.

It is also what tomorrow diffs against. Without a stored yesterday there is no
change line, only an assertion that something moved.

Two digests travel with every snapshot and they do different jobs:

  stable_sha256  what change detection compares, with per request noise removed
  raw_sha256     the digest of these exact bytes, so the stored file can be
                 shown to be the file that was fetched

Storing only the stable digest would mean the archive could be altered without
anything noticing, which would quietly undo the point of having an archive.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from google.cloud import storage

from .fetcher import Fetched

BUCKET = "migragent-snapshots"


def _path(source_id: str, read_at: str) -> str:
    """Sorted by source, then by time.

    The timestamp goes in the object name rather than relying on generations,
    because a human being should be able to look at the bucket and see the
    history without querying anything.
    """
    day = read_at[:10]
    stamp = read_at.replace(":", "").replace("-", "")
    return f"{source_id}/{day}/{stamp}.html"


@dataclass
class SnapshotStore:
    """Writes raw pages to Cloud Storage.

    The researcher holds storage.objectCreator and nothing more. Measured on
    18 August 2026 with a real object in the bucket, that principal gets
    Forbidden 403 on all four of read, overwrite, delete and list.

    So the archive is append only to the thing that fills it. An archive its own
    writer can revise is worth much less than one it cannot, because the whole
    job of these files is to still say tomorrow what the page said today.

    The list and read checks are in tools/test_isolation.py so this stays true
    rather than having been true once.
    """

    client: storage.Client
    bucket_name: str = BUCKET

    def store(self, source_id: str, result: Fetched) -> str | None:
        if not result.ok or result.body is None:
            return None

        blob_path = _path(source_id, result.read_at)
        blob = self.client.bucket(self.bucket_name).blob(blob_path)

        # Metadata rides with the object so a snapshot found on its own, months
        # later, still says what it is and when it was taken.
        blob.metadata = {
            "source_id": source_id,
            "url": result.url,
            "final_url": result.final_url or result.url,
            "read_at": result.read_at,
            "status": str(result.status),
            "stable_sha256": result.sha256 or "",
            "raw_sha256": result.raw_sha256 or "",
            "stored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        blob.upload_from_string(
            result.body,
            content_type=result.content_type or "text/html; charset=utf-8",
        )
        return f"gs://{self.bucket_name}/{blob_path}"
