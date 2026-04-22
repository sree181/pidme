"""
Image Discovery & Scoring Engine
Finds product images via DuckDuckGo image search and scores them
for relevance using URL analysis, title matching, and domain trust.
No GPU required — this is the lightweight scorer for MVP.
"""

import re
import asyncio
import logging
import hashlib
from typing import Optional
from dataclasses import dataclass
from rapidfuzz import fuzz
from ddgs import DDGS

logger = logging.getLogger(__name__)

# Domains known to host quality product images for industrial/B2B parts
TRUSTED_DOMAINS = {
    "skf.com": 1.0,
    "bearing.com": 0.95,
    "rbcbearings.com": 0.95,
    "dodge.com": 0.90,
    "nskindustrial.com": 0.90,
    "motion.com": 0.95,
    "grainger.com": 0.90,
    "mcmaster.com": 0.90,
    "fastenal.com": 0.85,
    "mscdirect.com": 0.85,
    "amazon.com": 0.60,
    "ebay.com": 0.50,
    "shopify": 0.65,
}

# URL patterns that suggest a product image (not logos, banners, etc.)
POSITIVE_URL_PATTERNS = [
    r"\d{4,}",          # SKU-like numbers in URL
    r"bearing",
    r"product",
    r"catalog",
    r"item",
    r"part",
    r"\.(jpg|jpeg|png|webp)$",
]

NEGATIVE_URL_PATTERNS = [
    r"logo",
    r"banner",
    r"icon",
    r"sprite",
    r"thumbnail.*tiny",
    r"avatar",
    r"placeholder",
]


@dataclass
class ScoredCandidate:
    image_url: str
    thumbnail_url: str
    source_domain: str
    source_query: str
    title: str
    url_relevance_score: float
    title_relevance_score: float
    domain_trust_score: float
    composite_score: float
    confidence_tier: str


def _extract_domain(url: str) -> str:
    match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return match.group(1) if match else ""


def _score_url_relevance(url: str, mfr_name: str, part_number: str) -> float:
    """
    Check if the image URL contains signals that suggest it's a product image
    for this specific part.
    """
    url_lower = url.lower()
    part_clean = re.sub(r"[^a-z0-9]", "", part_number.lower())

    score = 0.0

    # Does the URL contain the part number (cleaned)?
    if part_clean and len(part_clean) >= 4:
        if part_clean in re.sub(r"[^a-z0-9]", "", url_lower):
            score += 0.50

    # Does the URL contain the manufacturer name?
    mfr_clean = re.sub(r"\s+", "", mfr_name.lower())[:8]
    if mfr_clean and mfr_clean in url_lower:
        score += 0.20

    # Positive URL patterns
    pos_hits = sum(1 for p in POSITIVE_URL_PATTERNS if re.search(p, url_lower))
    score += min(pos_hits * 0.05, 0.20)

    # Negative URL patterns — heavy penalty
    neg_hits = sum(1 for p in NEGATIVE_URL_PATTERNS if re.search(p, url_lower))
    score -= neg_hits * 0.15

    return max(0.0, min(score, 1.0))


def _score_title_relevance(title: str, mfr_name: str, part_number: str, description: str) -> float:
    """
    Fuzzy match the image title/alt text against product metadata.
    """
    if not title:
        return 0.3  # Neutral when no title available

    title_lower = title.lower()

    # Direct part number match
    part_clean = re.sub(r"[^a-z0-9]", "", part_number.lower())
    title_clean = re.sub(r"[^a-z0-9]", "", title_lower)
    if part_clean and part_clean in title_clean:
        return 0.95

    # Fuzzy match on part number
    part_score = fuzz.token_set_ratio(part_number.lower(), title_lower) / 100

    # Fuzzy match on manufacturer name
    mfr_score = fuzz.partial_ratio(mfr_name.lower(), title_lower) / 100

    # Check for bearing-related keywords
    bearing_keywords = ["bearing", "brg", "ball bearing", "radial", "deep groove", "angular"]
    keyword_hit = any(kw in title_lower for kw in bearing_keywords)
    keyword_bonus = 0.10 if keyword_hit else 0.0

    score = (part_score * 0.55) + (mfr_score * 0.35) + keyword_bonus
    return min(score, 1.0)


def _score_domain_trust(domain: str) -> float:
    """
    Return trust score for the image source domain.
    Manufacturer and industrial distributor sites score highest.
    """
    domain_lower = domain.lower()

    # Exact match
    for trusted_domain, trust in TRUSTED_DOMAINS.items():
        if trusted_domain in domain_lower:
            return trust

    # Generic heuristics
    if any(x in domain_lower for x in ["industrial", "supply", "parts", "bearing"]):
        return 0.70
    if any(x in domain_lower for x in ["images", "cdn", "static", "media"]):
        return 0.60

    return 0.50  # Unknown domain: neutral


def _compute_composite(url_score: float, title_score: float, domain_score: float) -> tuple[float, str]:
    """
    Weighted fusion: title match is most important for B2B product images.
    """
    composite = (title_score * 0.50) + (url_score * 0.30) + (domain_score * 0.20)
    composite = round(composite, 4)

    if composite >= 0.75:
        tier = "high"
    elif composite >= 0.50:
        tier = "medium"
    else:
        tier = "low"

    return composite, tier


def search_product_images(
    mfr_name: str,
    part_number: str,
    description: str,
    max_results: int = 8,
) -> list[ScoredCandidate]:
    """
    Search DuckDuckGo for product images and score all candidates.
    Returns candidates sorted by composite_score descending.
    """
    candidates = []

    # Build 3 query variants to maximize coverage
    queries = [
        f"{mfr_name} {part_number} ball bearing product image",
        f"{part_number} bearing catalog photo",
        f"{mfr_name} {part_number} industrial bearing",
    ]

    seen_urls = set()
    engines = ["bing", "duckduckgo"]

    with DDGS() as ddgs:
        for query in queries:
            for engine in engines:
                try:
                    results = list(ddgs.images(
                        query,
                        max_results=max_results,
                        engine=engine,
                    ))

                    for r in results:
                        img_url = r.get("image", "")
                        if not img_url or img_url in seen_urls:
                            continue
                        seen_urls.add(img_url)

                        domain = _extract_domain(img_url)
                        title = r.get("title", "")

                        url_score = _score_url_relevance(img_url, mfr_name, part_number)
                        title_score = _score_title_relevance(title, mfr_name, part_number, description)
                        domain_score = _score_domain_trust(domain)
                        composite, tier = _compute_composite(url_score, title_score, domain_score)

                        candidates.append(ScoredCandidate(
                            image_url=img_url,
                            thumbnail_url=r.get("thumbnail", img_url),
                            source_domain=domain,
                            source_query=query,
                            title=title,
                            url_relevance_score=round(url_score, 4),
                            title_relevance_score=round(title_score, 4),
                            domain_trust_score=round(domain_score, 4),
                            composite_score=composite,
                            confidence_tier=tier,
                        ))
                    if results:
                        break
                except Exception as e:
                    logger.warning(f"Image search failed ({engine}) for '{query}': {e}")
                    continue

    # Sort by composite score descending, return top N
    candidates.sort(key=lambda c: c.composite_score, reverse=True)
    
    # Deduplicate by domain — keep at most 2 candidates per domain
    domain_counts: dict[str, int] = {}
    deduped = []
    for c in candidates:
        domain_counts[c.source_domain] = domain_counts.get(c.source_domain, 0) + 1
        if domain_counts[c.source_domain] <= 2:
            deduped.append(c)

    logger.info(
        f"Found {len(deduped)} candidates for {mfr_name} {part_number} "
        f"(top score: {deduped[0].composite_score if deduped else 'N/A'})"
    )
    return deduped
