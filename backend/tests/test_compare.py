"""
Unit tests for cross-market product comparison logic
"""
import pytest
from compare import (
    normalize_text,
    extract_features,
    title_similarity,
    token_overlap,
    score_match,
    best_match_for,
)


def test_normalize_text():
    raw = "Portátil Lenovo LOQ 15IAX9 Intel Core i5 12450HX 16GB SSD 512GB ¡Nuevo!"
    norm = normalize_text(raw)
    assert "portatil" in norm
    assert "¡" not in norm
    assert "!" not in norm
    assert "lenovo" in norm


def test_extract_features_laptop():
    title = "Laptop Dell Inspiron 15 3520 Intel Core i5 16GB RAM 512GB SSD 15.6\""
    feats = extract_features(title)
    assert feats["brand"] == "dell"
    assert feats["cpu"] == "i5"
    assert feats["ram"] == "16gb"
    assert feats["storage"] == "512gb"
    assert feats["screen"] == "15.6"
    assert "3520" in feats["model_codes"]


def test_extract_features_general_electronics():
    title_sony = "Sony WH-1000XM5 Audifonos Inalambricos Cancelacion Ruido Negro"
    feats_sony = extract_features(title_sony)
    assert feats_sony["brand"] == "sony"
    assert "wh-1000xm5" in feats_sony["model_codes"] or "1000xm5" in str(feats_sony["model_codes"])

    title_apple = "Apple iPhone 15 Pro Max 256GB Titanio Natural"
    feats_apple = extract_features(title_apple)
    assert feats_apple["brand"] == "apple"
    assert feats_apple["storage"] == "256gb"


def test_score_match_same_product():
    ml_title = "Portatil ASUS ROG Strix G16 Intel Core i7 16GB 512GB RTX 4060"
    amz_title = "ASUS ROG Strix G16 Gaming Laptop, 16” 165Hz FHD, GeForce RTX 4060, Intel Core i7, 16GB DDR5, 512GB PCIe SSD"

    f1 = extract_features(ml_title)
    f2 = extract_features(amz_title)

    score = score_match(f1, f2)
    assert score >= 0.65


def test_score_match_different_brands_penalized():
    ml_title = "Sony WH-1000XM5 Wireless Headphones"
    amz_title = "Bose QuietComfort 45 Wireless Noise Cancelling Headphones"

    f1 = extract_features(ml_title)
    f2 = extract_features(amz_title)

    score = score_match(f1, f2)
    assert score == 0.0  # Differing detected brands are filtered out


def test_best_match_for():
    base = extract_features("Apple MacBook Air 13 M2 8GB 256GB Gris Espacial")
    candidates = {
        101: extract_features("HP Pavilion 15 Intel i5 16GB 512GB"),
        102: extract_features("Apple MacBook Air 13.6\" Laptop M2 chip 8GB Memory 256GB SSD Space Gray"),
        103: extract_features("Lenovo IdeaPad 3 15.6\" Touchscreen Laptop"),
    }

    best_id, score = best_match_for(base, candidates)
    assert best_id == 102
    assert score > 0.60
