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
    "samsung", "huawei", "gigabyte", "razer", "microsoft", "sony",
    "nintendo", "logitech", "canon", "nikon", "xiaomi", "motorola",
    "lg", "bose", "jbl", "gopro", "dji", "google", "anker",
    "playstation", "xbox", "panasonic", "philips", "tcl", "hisense"
}

STOPWORDS = {
    "portatil", "portátil", "laptop", "notebook", "computador", "pc",
    "nuevo", "nueva", "oferta", "promo", "envio", "envío", "gratis",
    "original", "disponible", "color", "edition", "version", "modelo",
    "win", "windows", "home", "pro", "gen", "con", "sin", "de", "para",
    "y", "el", "la", "los", "las", "un", "una",
}

CPU_PATTERNS = [
    r"\bintel\s+core\s+i[3579]\b",
    r"\bi[3579]\b",
    r"\bcore\s+ultra\s*\d\b",
    r"\bultra\s*\d\b",
    r"\bryzen\s*[3579]\b",
    r"\bapple\s+m[1234]\b",
    r"\bm[1234]\b",
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


def extract_features(title: str) -> Dict[str, Optional[any]]:
    """
    Extract brand, model codes, cpu, ram, storage, screen from a title.
    Returns string/set values (normalized) or None.
    """
    norm = normalize_text(title)
    tokens = set(norm.split())

    # Detect brand
    brand = None
    for b in BRANDS:
        if b in tokens:
            brand = "hp" if b == "hewlett" else b
            break

    # Extract model codes (e.g. 3520, ps5, g15, wh-1000xm5, rtx4060, a54, s23)
    model_codes = set()
    for tok in tokens:
        if tok in STOPWORDS:
            continue
        if tok.isdigit() and len(tok) in (3, 4, 5) and tok not in {"2020", "2021", "2022", "2023", "2024", "2025", "2026"}:
            model_codes.add(tok)
        elif len(tok) >= 3 and any(c.isdigit() for c in tok) and any(c.isalpha() for c in tok):
            # Exclude simple storage/ram tokens like 8gb, 512gb, 1tb
            if re.match(r"^\d{1,4}(gb|tb|mb|hz|ghz|mah|w|p|k)$", tok):
                continue
            model_codes.add(tok)

    # CPU
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

    # RAM
    ram = None
    ram_match = re.search(r"(\d{1,2})\s?gb\s?(ram)?", norm)
    if ram_match:
        ram = f"{ram_match.group(1)}gb"

    # Storage
    storage = None
    storage_match = re.search(r"(\d{3,4})\s?gb|\b(\d)\s?tb\b", norm)
    if storage_match:
        if storage_match.group(1):
            storage = f"{storage_match.group(1)}gb"
        else:
            storage = f"{storage_match.group(2)}tb"

    # Screen (search in original title to preserve inch quote symbol)
    screen = None
    screen_match = re.search(r"(\d{2}(?:[.,]\d)?)\s*(?:\"|pulg|pulgadas|in\b)", title, re.IGNORECASE)
    if screen_match:
        screen = screen_match.group(1).replace(",", ".")

    return {
        "brand": brand,
        "model_codes": model_codes,
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


def score_match(a: Dict[str, Optional[any]], b: Dict[str, Optional[any]]) -> float:
    # If both have a detected brand and they differ, this is almost certainly NOT a match
    if a.get("brand") and b.get("brand") and a["brand"] != b["brand"]:
        return 0.0

    # Base weights
    weights = {
        "title": 0.35,
        "tokens": 0.25,
        "brand": 0.15,
        "model_codes": 0.25,
    }

    # Spec weights if present in either product
    has_specs = any([
        a.get("cpu") or b.get("cpu"),
        a.get("ram") or b.get("ram"),
        a.get("storage") or b.get("storage"),
        a.get("screen") or b.get("screen"),
    ])

    if has_specs:
        weights = {
            "title": 0.20,
            "tokens": 0.15,
            "brand": 0.15,
            "model_codes": 0.20,
            "cpu": 0.10,
            "ram": 0.08,
            "storage": 0.07,
            "screen": 0.05,
        }

    total_score = 0.0
    total_possible_weight = 0.0

    # Brand matching
    if a.get("brand") and b.get("brand"):
        total_possible_weight += weights["brand"]
        if a["brand"] == b["brand"]:
            total_score += weights["brand"]

    # Model code matching
    a_codes = a.get("model_codes") or set()
    b_codes = b.get("model_codes") or set()
    if a_codes and b_codes:
        total_possible_weight += weights["model_codes"]
        code_overlap = len(a_codes.intersection(b_codes)) / max(len(a_codes), len(b_codes))
        total_score += code_overlap * weights["model_codes"]
    elif a_codes or b_codes:
        total_possible_weight += weights["model_codes"] * 0.5

    # Specs
    if has_specs:
        for spec_key in ["cpu", "ram", "storage", "screen"]:
            val_a = a.get(spec_key)
            val_b = b.get(spec_key)
            if val_a and val_b:
                total_possible_weight += weights[spec_key]
                if val_a == val_b:
                    total_score += weights[spec_key]
            elif val_a or val_b:
                total_possible_weight += weights[spec_key] * 0.5

    # Text & token similarities
    total_possible_weight += weights["title"] + weights["tokens"]
    sim = title_similarity(a.get("norm_title", ""), b.get("norm_title", ""))
    overlap = token_overlap(a.get("norm_title", ""), b.get("norm_title", ""))

    total_score += sim * weights["title"]
    total_score += overlap * weights["tokens"]

    # Normalize by total possible weight to avoid artificially depressing scores of non-laptop items
    final_score = total_score / total_possible_weight if total_possible_weight > 0 else 0.0
    return round(min(1.0, final_score), 4)


def best_match_for(
    base_features: Dict[str, Optional[any]],
    candidates: Dict[int, Dict[str, Optional[any]]],
) -> Tuple[Optional[int], float]:
    best_id = None
    best_score = 0.0
    for pid, feats in candidates.items():
        s = score_match(base_features, feats)
        if s > best_score:
            best_score = s
            best_id = pid
    return best_id, best_score
