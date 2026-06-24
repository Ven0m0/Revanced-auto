"""Ad and tracker pattern data.

Ported from apk-tweak's ad_patterns.py.
Provides regex patterns commonly used for ad/tracker removal in smali files.
"""

from __future__ import annotations

import re
from re import Pattern

AdPattern = tuple[Pattern[str], str, str]

_RAW_PATTERNS: list[tuple[str, str, str]] = [
    (
        r'"ca-app-pub-\d{16}/\d{10}"',
        '"ca-app-pub-0000000000000000/0000000000"',
        "AdMob ID neutralization",
    ),
    (
        r'"(https?://|//).*?(googleads|googlesyndication|doubleclick|admob|'
        r'adservice|adsystem|advertising|analytics|crashlytics|firebase|'
        r'facebook\.com/tr|app-measurement).*?"',
        '"="',
        "Common ad/tracker URL neutralization",
    ),
    (
        r"invoke-[^}]+\{[^}]*\}, L[^;]+;->"
        r"(loadAd|showAd|requestInterstitialAd|showInterstitial|"
        r"loadRewardedAd|showRewardedAd|loadNativeAd|showNativeAd)\([^)]*\)V",
        "#",
        "Common ad invocation removal",
    ),
    (
        r"\.method [^(]*(loadAd|showAd|requestInterstitialAd|"
        r"showInterstitial|loadRewardedAd)\([^)]*\)V\s+\.locals \d+[\s\S]*?\.end method",
        "#",
        "Ad method stubbing",
    ),
]


def get_ad_patterns() -> list[AdPattern]:
    """Return compiled ad/tracker patterns with replacements.

    Returns:
        List of tuples: (compiled_pattern, replacement, description).
    """
    return [
        (re.compile(pattern, re.IGNORECASE), replacement, description)
        for pattern, replacement, description in _RAW_PATTERNS
    ]


def get_tracker_domains() -> set[str]:
    """Return a set of common tracker/advertising domain substrings."""
    return {
        "googleads",
        "googlesyndication",
        "doubleclick",
        "admob",
        "google-analytics",
        "firebaseanalytics",
        "crashlytics",
        "facebook.com/tr",
        "app-measurement",
        "appsflyer",
        "adjust",
        "mixpanel",
        "amplitude",
        "segment",
        "braze",
        "moengage",
    }
