"""
Product comparison utilities for cross-market matching.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, Optional, Tuple, Set

BRANDS = {
    "hp", "hewlett", "dell", "lenovo", "asus", "acer", "msi", "apple",
    "samsung", "huawei", "gigabyte", "razer", "microsoft",
}

STOPWORDS = {
    "portatil", "portátil", "laptop", "notebook", "computador", "pc",
    "nuevo", "nueva", "oferta", "promo", "envio", "envío", "gratis",
    "original", "disponible", "color", "edition", "version", "modelo",
    "win", "windows", "home", "pro",
}

CPU_PATTERNS = [
    r"\bintel\s+core\s+i[3579]\b",
    r"\bi[3579]\b",
    r"\bcore\s+ultra\s*\d\b",
    r"\bultra\s*\d\b",
    r"\bryzen\s*[3579]\b",
    r"\bapple\s+m[123]\b",
    r"\bm[123]\b",
]


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = _strip_accents(text.lower())
    text = re.sub(r"[^\w\s\.]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _token_set(text: str) -> Set[str]:
    if not text:
        return set()
    norm = normalize_text(text)
    tokens = []
    for t in norm.split():
        if t in STOPWORDS:
            continue
        if t in {"portatil", "portátil", "notebook"}:
            t = "laptop"
        tokens.append(t)
    return set(tokens)


def extract_features(title: str) -> Dict[str, Optional[str]]:
    """
    Extract brand, cpu, ram, storage, screen from a title.
    Returns string values (normalized) or None.
    """
    norm = normalize_text(title)
    tokens = set(norm.split())

    brand = None
    for b in BRANDS:
        if b in tokens:
            brand = "hp" if b == "hewlett" else b
            break

    cpu = None
    for pattern in CPU_PATTERNS:
        match = re.search(pattern, norm)
        if match:
            cpu = (
                match.group(0)
                .replace("intel core ", "")
                .replace("core ", "")
                .replace(" ", "")
            )
            break

    ram = None
    ram_match = re.search(r"(\d{1,2})\s?gb\s?(ram)?", norm)
    if ram_match:
        ram = f"{ram_match.group(1)}gb"

    storage = None
    storage_match = re.search(r"(\d{3,4})\s?gb|\b(\d)\s?tb\b", norm)
    if storage_match:
        if storage_match.group(1):
            storage = f"{storage_match.group(1)}gb"
        else:
            storage = f"{storage_match.group(2)}tb"

    screen = None
    screen_match = re.search(r"(\d{2}([.,]\d)?)\s?\"", norm)
    if screen_match:
        screen = screen_match.group(1).replace(",", ".")

    return {
        "brand": brand,
        "cpu": cpu,
        "ram": ram,
        "storage": storage,
        "screen": screen,
        "norm_title": norm,
    }


def title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a = normalize_text(a)
    b = normalize_text(b)

    a_tokens = [t for t in a.split() if t not in STOPWORDS]
    b_tokens = [t for t in b.split() if t not in STOPWORDS]
    a_clean = " ".join(a_tokens)
    b_clean = " ".join(b_tokens)

    return SequenceMatcher(None, a_clean, b_clean).ratio()


def token_overlap(a: str, b: str) -> float:
    a_set = _token_set(a)
    b_set = _token_set(b)
    if not a_set or not b_set:
        return 0.0
    inter = a_set.intersection(b_set)
    return len(inter) / max(len(a_set), len(b_set))


def score_match(a: Dict[str, Optional[str]], b: Dict[str, Optional[str]]) -> float:
    weights = {
        "brand": 0.15,
        "cpu": 0.20,
        "ram": 0.10,
        "storage": 0.10,
        "screen": 0.10,
        "title": 0.20,
        "tokens": 0.15,
    }

    score = 0.0
    if a.get("brand") and b.get("brand") and a["brand"] == b["brand"]:
        score += weights["brand"]
    if a.get("cpu") and b.get("cpu") and a["cpu"] == b["cpu"]:
        score += weights["cpu"]
    if a.get("ram") and b.get("ram") and a["ram"] == b["ram"]:
        score += weights["ram"]
    if a.get("storage") and b.get("storage") and a["storage"] == b["storage"]:
        score += weights["storage"]
    if a.get("screen") and b.get("screen") and a["screen"] == b["screen"]:
        score += weights["screen"]

    score += title_similarity(a.get("norm_title", ""), b.get("norm_title", "")) * weights["title"]
    score += token_overlap(a.get("norm_title", ""), b.get("norm_title", "")) * weights["tokens"]
    return round(score, 4)


def best_match_for(
    base_features: Dict[str, Optional[str]],
    candidates: Dict[int, Dict[str, Optional[str]]],
) -> Tuple[Optional[int], float]:
    best_id = None
    best_score = 0.0
    for pid, feats in candidates.items():
        s = score_match(base_features, feats)
        if s > best_score:
            best_score = s
            best_id = pid
    return best_id, best_score
