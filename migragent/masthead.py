"""The masthead every page wears.

One masthead, so the site reads as one paper. Its styles live in
web/brand/tokens.css under "The masthead", because every page already loads
that file, and a header that each page restyled for itself is how the site
ended up with sixteen slightly different ones.

The top line is the agent's: when it last filed, whether it is reading now,
and what $MIGRA is worth. It comes from /api/state, the same figures as the
front page desk, and until that answers it says nothing rather than guessing.
"""
from __future__ import annotations

# The mark: the M, and a smile under it. Defined here, not in result_page, so
# that every page can import the masthead without a circular import.
LOGO = ('<svg viewBox="0 0 64 64"><path d="M10 36 V8 L32 28 L54 8 V36" fill="none" '
        'stroke="currentColor" stroke-width="9" stroke-linecap="round" '
        'stroke-linejoin="round"/><path d="M19 50 Q32 61 45 50" fill="none" '
        'stroke="currentColor" stroke-width="7.5" stroke-linecap="round"/></svg>')

NAV = (
    ("/articles", "The wire"),
    ("/start", "Where you qualify"),
    ("/dashboard", "Your case"),
    ("/rounds", "The desk"),
    ("/coverage", "Coverage"),
    ("/subscribe", "$MIGRA"),
    ("/data", "Your data"),
)

MASTHEAD = (
    '<header class="mast">'
    '<div class="mast-top">'
    '<span><b id="mh-date"></b> <span class="hide-sm" id="mh-filed"></span></span>'
    '<span><span class="mast-live idle" id="mh-live"><i></i><span id="mh-phase">The agent</span></span>'
    ' <span class="hide-sm" id="mh-token"></span></span>'
    '</div>'
    f'<a class="mast-name" href="/">{LOGO}<span>MIGRAGENT</span></a>'
    '<p class="mast-tag">The immigration wire. Written by an agent that reads the rules every morning.</p>'
    '<nav class="mast-nav" aria-label="Sections">'
    + "".join(f'<a href="{href}">{label}</a>' for href, label in NAV)
    + '</nav></header>'
    '<script>(() => {'
    'const $ = (i) => document.getElementById(i);'
    '$("mh-date").textContent = new Date().toLocaleDateString("en-GB",'
    ' {weekday: "long", day: "numeric", month: "long", year: "numeric"});'
    'for (const a of document.querySelectorAll(".mast-nav a")) {'
    ' const h = a.getAttribute("href");'
    ' if (location.pathname === h || location.pathname.startsWith(h + "/")) a.setAttribute("aria-current", "page"); }'
    'fetch("/api/state").then((r) => r.json()).then((s) => {'
    ' const t = (iso) => new Date(iso).toISOString().slice(11, 16) + " UTC";'
    ' if (s.status.last_round_at) $("mh-filed").textContent = "\\u00b7 last filed by the agent " + t(s.status.last_round_at);'
    ' const reading = s.status.phase === "READING";'
    ' $("mh-live").className = "mast-live" + (reading ? "" : " idle");'
    ' $("mh-phase").textContent = reading ? "Reading now" : "Next: " + s.status.next.what + " " + t(s.status.next.at);'
    ' if (s.token) $("mh-token").textContent = "\\u00b7 $MIGRA $" + (s.token.market_cap_usd / 1000).toFixed(1) + "K";'
    '}).catch(() => {});'
    '})();</script>'
)
