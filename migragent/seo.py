"""What search engines and link previews read: one helper, every page.

Each page passes its own title, description and path, and gets back the tags
that go in its <head>: a canonical URL, Open Graph and Twitter cards, and
structured data. Articles are marked up as NewsArticle, with the date the page
changed and the date the article was written, published by MIGRAGENT.

Titles are cut at a word, not mid-word, and kept under 65 characters, because
that is about where Google stops showing them. Descriptions are kept under 160.
The full headline still goes into Open Graph and the structured data, where
there is room for it.
"""
from __future__ import annotations

import html
import json
from typing import Any

SITE = "https://migragent.onenept.com"
NAME = "MIGRAGENT"
OG_IMAGE = f"{SITE}/brand/og-default.png"
LOGO_PNG = f"{SITE}/brand/telegram/migragent-logo.png"


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""), quote=True)


def clip(text: str, limit: int) -> str:
    """Cut at a word boundary, under `limit` characters, with no trailing punctuation."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:.-")
    return cut + "…"


def page_title(title: str, brand: bool = True) -> str:
    suffix = f" | {NAME}"
    room = 65 - (len(suffix) if brand else 0)
    t = clip(title, room)
    return t + suffix if brand and len(t) + len(suffix) <= 65 else t


def meta(*, title: str, description: str, path: str, kind: str = "website",
         image: str = OG_IMAGE, ld: list[dict[str, Any]] | None = None,
         published: str = "", modified: str = "", noindex: bool = False) -> str:
    """Everything for <head> after the shared HEAD: title, description, canonical, cards, JSON-LD."""
    url = SITE + path
    desc = clip(description, 160)
    tags = [
        f"<title>{_e(page_title(title))}</title>",
        f'<meta name="description" content="{_e(desc)}">',
        f'<link rel="canonical" href="{_e(url)}">',
        f'<meta property="og:site_name" content="{NAME}">',
        f'<meta property="og:type" content="{_e(kind)}">',
        f'<meta property="og:title" content="{_e(clip(title, 95))}">',
        f'<meta property="og:description" content="{_e(desc)}">',
        f'<meta property="og:url" content="{_e(url)}">',
        f'<meta property="og:image" content="{_e(image)}">',
        '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:site" content="@migragent">',
        f'<meta name="twitter:title" content="{_e(clip(title, 70))}">',
        f'<meta name="twitter:description" content="{_e(desc)}">',
        f'<meta name="twitter:image" content="{_e(image)}">',
        '<link rel="alternate" type="application/rss+xml" title="MIGRAGENT, the wire" href="/feed.xml">',
    ]
    if published:
        tags.append(f'<meta property="article:published_time" content="{_e(published)}">')
    if modified:
        tags.append(f'<meta property="article:modified_time" content="{_e(modified)}">')
    if noindex:
        tags.append('<meta name="robots" content="noindex, nofollow">')
    for block in ld or []:
        # "</" cannot appear inside a script block, or the page could be closed early.
        tags.append('<script type="application/ld+json">'
                    + json.dumps(block, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    return "\n".join(tags)


def organization() -> dict[str, Any]:
    return {"@context": "https://schema.org", "@type": "NewsMediaOrganization", "name": NAME,
            "url": SITE, "logo": {"@type": "ImageObject", "url": LOGO_PNG},
            "sameAs": ["https://x.com/migragent"]}


def website() -> dict[str, Any]:
    return {"@context": "https://schema.org", "@type": "WebSite", "name": f"{NAME}, the immigration wire",
            "url": SITE}


def news_article(*, headline: str, description: str, path: str, published: str, modified: str,
                 country: str, sources: list[str]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": clip(headline, 110), "description": clip(description, 160),
        "mainEntityOfPage": SITE + path, "url": SITE + path, "image": [OG_IMAGE],
        "datePublished": published, "dateModified": modified or published,
        "author": {"@type": "Organization", "name": NAME, "url": SITE},
        "publisher": {"@type": "Organization", "name": NAME, "logo": {"@type": "ImageObject", "url": LOGO_PNG}},
        "about": {"@type": "Country", "name": country}, "isBasedOn": sources[:10],
        "inLanguage": "en",
    }


def breadcrumbs(*crumbs: tuple[str, str]) -> dict[str, Any]:
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i, "name": n, "item": SITE + p}
                                for i, (n, p) in enumerate(crumbs, 1)]}
