"""What the reading job has actually been doing, on a page instead of in a console.

WHY THIS EXISTS
---------------
The crawl is the half of this product nobody can see. It runs at 04:40 while
everybody is asleep, it writes what it did to the `rounds` collection, and until
now the only way to look at that was `gcloud` or the Cloud Run console. So the
one claim the whole thing rests on, that it keeps reading after you close the
tab, was the one claim a person had to take on trust.

Every number here is read off a row the job wrote when it finished. Nothing is
computed for the page and nothing is estimated. A round that failed appears as a
failed round, because a status page that only shows the good rounds is not a
status page.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not call the Cloud Run Admin API to list executions. The web identity
cannot become the watcher and is not getting a new role so a page can look
prettier, which is Decision 5. What the job wrote is what the job did, and that
is already in Firestore where this service is allowed to read.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

from .flow_page import STYLE
from .result_page import HEAD, LOGO

# What Cloud Scheduler starts, and when. Written here rather than read from the
# scheduler API for the same reason as above: no new role for a label. These are
# the four jobs in docs/ARCHITECTURE.md and they are checked against it.
SCHEDULE = (
    ("03:17", "retention sweep", "deletes every case past its window"),
    ("04:40", "watch round", "re-reads what we hold, and works out what moved"),
    ("05:00", "job listings", "new postings off government boards"),
    ("05:20", "digest", "who does today's changes affect, and tell them"),
)

MODE_WORDS = {
    "watch": "re-read what we hold",
    "extract": "read pages nobody had read",
    "listings": "pulled government job postings",
    "digest": "worked out who needed telling",
    "selftest": "checked its own boundary",
    "robots": "printed robots.txt as received",
}


def _e(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def _ago(iso: str) -> str:
    """How long ago, in words. An unparseable date says so rather than guessing."""
    if not iso:
        return "never"
    try:
        then = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return _e(iso)
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    seconds = (datetime.now(timezone.utc) - then).total_seconds()
    if seconds < 0:
        return "just now"
    if seconds < 90:
        return f"{int(seconds)} seconds ago"
    if seconds < 5400:
        return f"{int(seconds // 60)} minutes ago"
    if seconds < 172800:
        return f"{int(seconds // 3600)} hours ago"
    return f"{int(seconds // 86400)} days ago"


def _clock(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %H:%M")
    except (ValueError, TypeError):
        return _e(iso) or "unknown"


def _n(row: dict[str, Any], key: str) -> int:
    try:
        return int(row.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _round_row(row: dict[str, Any]) -> str:
    mode = str(row.get("mode", ""))
    lane = f'{row.get("jurisdiction", "")} {row.get("lane", "")}'.strip()
    failed = _n(row, "failed")
    fetched = _n(row, "fetched")
    unchanged = _n(row, "unchanged")
    changed = _n(row, "changed")
    kept = _n(row, "kept")
    dropped = _n(row, "dropped")
    off_lane = _n(row, "off_lane")
    material = _n(row, "material_changes")
    seconds = row.get("seconds") or 0

    # A round that finished is a round that wrote a finish time. One that did
    # not is reported as unfinished rather than quietly rendered as a success.
    finished = bool(row.get("finished_at"))
    if not finished:
        state, word = "bad", "did not finish"
    elif failed:
        state, word = "warn", f"{failed} failed"
    else:
        state, word = "ok", "clean"

    facts = []
    if fetched:
        facts.append(f"<b>{fetched}</b> fetched")
    if unchanged:
        facts.append(f"<b>{unchanged}</b> unchanged, so nothing was re-read")
    if changed:
        facts.append(f"<b>{changed}</b> moved")
    if material:
        facts.append(f"<b>{material}</b> material")
    if kept:
        facts.append(f"<b>{kept}</b> requirements kept")
    if dropped:
        facts.append(f"<b>{dropped}</b> dropped for a quote that was not on the page")
    if off_lane:
        facts.append(f"<b>{off_lane}</b> off lane")
    if not facts:
        facts.append("nothing to do on this pass")

    return f'''
    <tr class="r {state}">
      <td class="when"><b>{_clock(str(row.get("started_at", "")))}</b>
        <span>{_e(_ago(str(row.get("started_at", ""))))}</span></td>
      <td class="lane"><b>{_e(lane)}</b>
        <span>{_e(MODE_WORDS.get(mode, mode))}</span></td>
      <td class="facts">{" &middot; ".join(facts)}</td>
      <td class="took">{float(seconds):.0f}s</td>
      <td><span class="state {state}">{_e(word)}</span></td>
    </tr>'''


def _change_row(row: dict[str, Any]) -> str:
    summary = row.get("summary") or "no sentence was written for this one"
    by = row.get("summary_by") or ""
    return f'''
    <li>
      <div class="ch-top">
        <span class="ch-lane">{_e(row.get("jurisdiction", ""))} {_e(row.get("lane", ""))}</span>
        <span class="ch-when">{_e(_clock(str(row.get("after_read_at", ""))))}</span>
      </div>
      <p class="ch-sum">{_e(summary)}</p>
      <p class="ch-cite">
        <a href="{_e(row.get("source_url", ""))}">{_e(row.get("source_url", ""))}</a>
        <span>+{_n(row, "added")} / -{_n(row, "removed")} lines{
          f" &middot; sentence written by {_e(by)}" if by else ""}</span>
      </p>
    </li>'''


def rounds_html(rounds: list[dict[str, Any]], changes: list[dict[str, Any]],
                sources: int, read_sources: int, requirements: int) -> str:
    """The page. Every figure comes in as an argument that was read from a row."""
    last = rounds[0] if rounds else None
    last_when = _ago(str(last.get("started_at", ""))) if last else "never"

    clean = sum(1 for r in rounds if r.get("finished_at") and not _n(r, "failed"))
    fetched = sum(_n(r, "fetched") for r in rounds)
    unchanged = sum(_n(r, "unchanged") for r in rounds)
    moved = sum(_n(r, "changed") for r in rounds)

    schedule = "".join(
        f'<tr><td class="t">{_e(t)}</td><td><b>{_e(name)}</b></td>'
        f'<td class="why">{_e(why)}</td></tr>'
        for t, name, why in SCHEDULE)

    round_rows = "".join(_round_row(r) for r in rounds) or (
        '<tr><td colspan="5" class="none">No rounds have been recorded yet. '
        'That is what an empty pipeline looks like, and it is not being dressed '
        'up as anything else.</td></tr>')

    change_items = "".join(_change_row(c) for c in changes) or (
        '<li class="none">Nothing has moved on the pages we watch since the last '
        'sweep. That is a real answer and the common one: most government pages '
        'do not change most days.</li>')

    return f'''<!doctype html>
<html lang="en" data-theme="dark"><head>{HEAD}
<title>What the reading job did</title>
<style>{STYLE}
  .lede {{ color: var(--ink-soft); line-height: 1.7; max-width: 66ch; margin: 0 0 30px }}
  .tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(158px, 1fr));
            gap: 12px; margin-bottom: 40px }}
  .tile {{ background: var(--paper-raised); border: 1px solid var(--rule);
           border-radius: var(--radius); padding: 15px 17px }}
  .tile b {{ display: block; font-family: var(--font-display); font-size: 1.5rem;
             line-height: 1.1; margin-bottom: 5px; font-variant-numeric: tabular-nums }}
  .tile span {{ font: 500 .68rem/1.4 var(--font-body); text-transform: uppercase;
                letter-spacing: .1em; color: var(--ink-soft) }}
  h2 {{ font-family: var(--font-display); font-size: 1.2rem; margin: 0 0 6px }}
  .sub2 {{ color: var(--ink-soft); font-size: .92rem; line-height: 1.65;
           margin: 0 0 18px; max-width: 66ch }}
  section {{ margin-bottom: 46px }}
  .scroll {{ overflow-x: auto; border: 1px solid var(--rule);
             border-radius: var(--radius); background: var(--paper-raised) }}
  table {{ width: 100%; border-collapse: collapse; font-size: .88rem; min-width: 660px }}
  th {{ text-align: left; font: 500 .67rem/1 var(--font-body); text-transform: uppercase;
        letter-spacing: .1em; color: var(--ink-soft); padding: 13px 15px;
        border-bottom: 1px solid var(--rule); white-space: nowrap }}
  td {{ padding: 12px 15px; border-bottom: 1px solid var(--rule); vertical-align: top }}
  tr:last-child td {{ border-bottom: none }}
  td.when b, td.lane b {{ display: block; font-weight: 600 }}
  td.when span, td.lane span {{ color: var(--ink-soft); font-size: .8rem }}
  td.when {{ white-space: nowrap; font-variant-numeric: tabular-nums }}
  td.facts {{ color: var(--ink-soft); line-height: 1.6 }}
  td.facts b {{ color: var(--ink); font-variant-numeric: tabular-nums }}
  td.took {{ font-family: var(--font-mono); font-size: .8rem; color: var(--ink-soft);
             text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums }}
  td.t {{ font-family: var(--font-mono); color: var(--primary); white-space: nowrap }}
  td.why {{ color: var(--ink-soft) }}
  .state {{ display: inline-block; font: 500 .66rem/1 var(--font-body);
            text-transform: uppercase; letter-spacing: .09em; padding: 5px 9px;
            border-radius: 100px; white-space: nowrap; border: 1px solid var(--rule) }}
  .state.ok {{ color: var(--accent); border-color: var(--accent) }}
  .state.warn {{ color: var(--warn); border-color: var(--warn) }}
  .state.bad {{ color: var(--warn); border-color: var(--warn); font-weight: 600 }}
  .none {{ color: var(--ink-soft); line-height: 1.7 }}
  ul.changes {{ list-style: none; margin: 0; padding: 0 }}
  ul.changes li {{ border-left: 2px solid var(--rule); padding: 2px 0 2px 16px;
                   margin-bottom: 20px }}
  ul.changes li.none {{ border-left-color: var(--rule); padding-left: 16px }}
  .ch-top {{ display: flex; gap: 12px; align-items: baseline; margin-bottom: 5px }}
  .ch-lane {{ font: 500 .66rem/1 var(--font-body); text-transform: uppercase;
              letter-spacing: .1em; color: var(--primary) }}
  .ch-when {{ font-family: var(--font-mono); font-size: .72rem; color: var(--ink-soft) }}
  .ch-sum {{ margin: 0 0 6px; line-height: 1.6 }}
  .ch-cite {{ margin: 0; font-size: .78rem; line-height: 1.7 }}
  .ch-cite a {{ font-family: var(--font-mono); color: var(--link); word-break: break-all }}
  .ch-cite span {{ display: block; color: var(--ink-soft); font-family: var(--font-mono) }}
  .foot {{ color: var(--ink-soft); font-size: .84rem; line-height: 1.7;
           border-top: 1px solid var(--rule); padding-top: 20px; max-width: 70ch }}
</style></head>
<body><main>
  <div class="brand">{LOGO}<span>MIGRAGENT</span></div>

  <h1>What the reading job did</h1>
  <p class="lede">Nobody starts these. Cloud Scheduler does, four times before six in the morning,
  and the job writes down what it found. Every number on this page was read off a row that job
  wrote when it finished, including the rounds that failed. The last one ran
  <b>{_e(last_when)}</b>.</p>

  <div class="tiles">
    <div class="tile"><b>{len(rounds)}</b><span>rounds recorded</span></div>
    <div class="tile"><b>{clean}</b><span>finished clean</span></div>
    <div class="tile"><b>{fetched}</b><span>pages fetched</span></div>
    <div class="tile"><b>{unchanged}</b><span>unchanged, cost nothing</span></div>
    <div class="tile"><b>{moved}</b><span>pages that moved</span></div>
    <div class="tile"><b>{requirements}</b><span>requirements held</span></div>
  </div>

  <section>
    <h2>What runs, and when</h2>
    <p class="sub2">The order is the point. Read the government pages first, then ask the job
    boards, then work out who needs telling. Run the digest first and it reports on yesterday.</p>
    <div class="scroll"><table>
      <thead><tr><th>UTC</th><th>Job</th><th>What it is for</th></tr></thead>
      <tbody>{schedule}</tbody>
    </table></div>
  </section>

  <section>
    <h2>The rounds themselves</h2>
    <p class="sub2">Newest first. A page whose bytes did not move is never re-read and never sent
    to a model, which is why the unchanged column is usually the biggest one and why a round that
    does almost nothing is a round working correctly.</p>
    <div class="scroll"><table>
      <thead><tr><th>Started</th><th>Lane</th><th>What it did</th><th>Took</th><th></th></tr></thead>
      <tbody>{round_rows}</tbody>
    </table></div>
  </section>

  <section>
    <h2>What actually moved</h2>
    <p class="sub2">Both versions are kept with both dates. The sentence about what changed is
    written by a model and says so; the counts underneath it are measured.</p>
    <ul class="changes">{change_items}</ul>
  </section>

  <p class="foot">Read from the same store the job writes to, not from a copy.
  {read_sources} of {sources} registered pages have been read at least once. This page does not
  ask the Cloud Run API what happened, because the web service cannot become the watcher and is
  not getting a new role so a page can look busier. <a href="/architecture">How it is put
  together</a> &middot; <a href="/coverage">Everything we have read</a> &middot;
  <a href="/">Back to the start</a></p>
</main></body></html>'''
