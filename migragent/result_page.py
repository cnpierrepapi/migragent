"""The shared <head> every page loads, and the mark and masthead re-exported.

This file used to render the case result page. That product was removed on
2 October 2026; the name stays because every page imports HEAD from here.
"""
from __future__ import annotations

from .masthead import LOGO, MASTHEAD  # noqa: F401

HEAD = '''<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="/brand/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:ital,opsz,wght@0,8..60,400..700;1,8..60,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/brand/tokens.css">'''
