"""Measure contrast ratios for the brand palette.

Exists because the palette must not claim a WCAG level in a document before
something has measured it. Run it, read the numbers, write the numbers down.

    python tools/contrast.py
"""
from __future__ import annotations

import sys

LIGHT = {
    "paper": "#FCFAF6",
    "paper_raised": "#FFFFFF",
    "ink": "#15191E",
    "ink_soft": "#5A6472",
    "rule": "#E4DFD6",
    "primary": "#0B6E4F",
    "primary_hot": "#12A16F",
    "accent": "#FFC53D",
    "link": "#1C5FCF",
    "warn": "#B4442A",
}

DARK = {
    "paper": "#0B0D10",
    "paper_raised": "#14181D",
    "ink": "#E9EBEE",
    "ink_soft": "#99A2AE",
    "rule": "#232A32",
    "primary": "#3DD68C",
    "primary_hot": "#6FE7AE",
    "accent": "#C9A227",
    "link": "#8FB3F5",
    "warn": "#E0765A",
}

# Every pair that carries text somewhere in the product. Anything not listed
# here is decoration and must never be used for text.
TEXT_PAIRS = [
    ("ink", "paper"),
    ("ink", "paper_raised"),
    ("ink_soft", "paper"),
    ("primary", "paper"),
    ("primary_hot", "paper"),
    ("link", "paper"),
    ("warn", "paper"),
    ("accent", "paper"),
]


def _channel(value: float) -> float:
    value = value / 255
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    hex_colour = hex_colour.lstrip("#")
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def ratio(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def grade(value: float) -> str:
    if value >= 7.0:
        return "AAA body"
    if value >= 4.5:
        return "AA body"
    if value >= 3.0:
        return "AA large only"
    return "DECORATION ONLY, never text"


def report(name: str, palette: dict[str, str]) -> int:
    print(f"\n{name}")
    print("-" * 62)
    failures = 0
    for fg, bg in TEXT_PAIRS:
        value = ratio(palette[fg], palette[bg])
        verdict = grade(value)
        if value < 4.5:
            failures += 1
        print(f"  {fg:<12} on {bg:<12} {value:6.2f}  {verdict}")
    return failures


if __name__ == "__main__":
    report("LIGHT, bright and youthful", LIGHT)
    report("DARK, elite and mature", DARK)
    print("\nA number below 4.50 is not a bug by itself. It means that colour is")
    print("a fill or a rule, and the palette notes must say so.")
    sys.exit(0)
