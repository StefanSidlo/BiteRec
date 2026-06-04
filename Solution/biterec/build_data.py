"""
build_data.py  --  BiteRec data preparation
================================================

Turns a raw Open Food Facts CSV export into a small, clean `products.json`
catalog that the BiteRec web app can serve instantly.

WHY THIS STEP EXISTS
--------------------
The raw OFF dump is huge and very sparse: most rows are missing a Nutri-Score,
an Eco-Score, or the basic nutrient values. For a live demo we only want
products that have *enough real data* for the recommendations to make sense.
This script keeps only products that have:

  * a product name
  * a valid Nutri-Score grade (a-e)
  * a valid Eco-Score / Environmental-Score grade (a-e)
  * the core nutrients (energy, fat, sugar, protein)

It also derives the things the raw data does NOT contain reliably:

  * per-product allergen flags (from ingredients / allergens / traces text)
  * estimated CO2 and water footprints (the raw `carbon-footprint_100g`
    column is empty in almost every row, so we estimate from the Eco-Score
    grade + product category, and clearly label these as estimates in the UI)

USAGE
-----
    python build_data.py                       # uses data/openfoodfacts_short_30MB.csv
    python build_data.py path/to/any_off.csv   # works on any OFF-format export

The script is dataset-agnostic: point it at the full OFF dump and it will
produce a clean catalog the same way.
"""

import sys
import os
import json
import math
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(HERE, "data", "openfoodfacts_short_30MB.csv")
OUT_JSON = os.path.join(HERE, "data", "products.json")

# Columns we read from the (potentially enormous) CSV. Reading a subset keeps
# memory usage low even on the full Open Food Facts dump.
USECOLS = [
    "code", "url", "product_name", "brands", "categories_en",
    "countries_en", "image_url", "image_small_url",
    "nutriscore_grade", "environmental_score_grade", "environmental_score_score", "nova_group",
    "pnns_groups_1", "pnns_groups_2",
    "labels_en", "origins_en", "ingredients_text", "ingredients_tags",
    "allergens", "traces_en", "additives_n",
    "energy-kcal_100g", "fat_100g", "saturated-fat_100g", "sugars_100g",
    "salt_100g", "proteins_100g", "fiber_100g", "sodium_100g",
]

# Nutrients we try hard to keep. The first four are required; the rest are
# imputed to 0 when missing (OFF commonly omits fiber/salt for products that
# genuinely contain none -- the ML notebook does the same).
REQUIRED_NUTRIENTS = ["energy-kcal_100g", "fat_100g", "sugars_100g", "proteins_100g"]
OPTIONAL_NUTRIENTS = ["saturated-fat_100g", "salt_100g", "fiber_100g", "sodium_100g"]

VALID_GRADES = {"a", "b", "c", "d", "e"}

# ---------------------------------------------------------------------------
# Allergen detection
# ---------------------------------------------------------------------------
# OFF's structured allergen columns are almost empty, so we scan the free-text
# ingredient/allergen/trace fields for keywords. Maps the 14 EU major allergens.
ALLERGEN_KEYWORDS = {
    "gluten":    ["gluten", "wheat", "barley", "rye", "spelt", "oat", "flour", "malt", "triga", "trigo", "cebada"],
    "milk":      ["milk", "lactose", "cheese", "butter", "cream", "whey", "casein", "yogurt", "leche", "lait", "latte"],
    "eggs":      ["egg", "albumin", "huevo", "oeuf", "uovo"],
    "soy":       ["soy", "soya", "soja", "lecithin (soy)", "soybean"],
    "nuts":      ["almond", "hazelnut", "walnut", "cashew", "pecan", "pistachio", "macadamia", "nut", "almendra", "nuez"],
    "peanuts":   ["peanut", "groundnut", "cacahuete", "arachide"],
    "fish":      ["fish", "anchovy", "tuna", "salmon", "cod", "pescado", "poisson"],
    "shellfish": ["shrimp", "prawn", "crab", "lobster", "crustacean", "shellfish", "mollusc", "mussel", "clam", "squid"],
    "sesame":    ["sesame", "tahini", "sesamo"],
    "celery":    ["celery", "celeriac", "apio"],
    "mustard":   ["mustard", "mostaza", "moutarde"],
    "sulphites": ["sulphite", "sulfite", "sulphur dioxide", "e220", "e221", "e222", "e223", "e224", "e228"],
    "lupin":     ["lupin", "lupine"],
}

# ---------------------------------------------------------------------------
# Eco footprint estimation
# ---------------------------------------------------------------------------
# The raw `carbon-footprint_100g` column is empty for ~all rows, so we estimate
# from (a) a category baseline (rough life-cycle CO2 / water per kg, from public
# LCA literature) and (b) the product's Eco-Score grade as a multiplier.
# These are deliberately coarse and ALWAYS shown as "estimated" in the UI.
# Baseline = (kg CO2e per kg of product, litres of water per kg of product).
CATEGORY_FOOTPRINT = {
    "Fish Meat Eggs":          (12.0, 4200),
    "Milk and dairy products": (4.5, 1800),
    "Fat and sauces":          (3.8, 1500),
    "Composite foods":         (3.2, 1300),
    "Sugary snacks":           (2.6, 1400),
    "Cereals and potatoes":    (1.4, 900),
    "Salty snacks":            (2.2, 1100),
    "Beverages":               (0.8, 600),
    "Fruits and vegetables":   (0.7, 500),
    "unknown":                 (2.0, 1000),
}
# Eco-Score grade -> multiplier on the category baseline (A is best/lowest).
ECO_GRADE_MULT = {"a": 0.55, "b": 0.78, "c": 1.0, "d": 1.35, "e": 1.8}

# 1 kg CO2e is roughly equivalent to driving ~5.7 km in an average petrol car.
CO2_TO_CAR_KM = 5.7


def _to_float(v):
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def detect_allergens(*texts):
    """Return a sorted list of allergen keys found in any of the given texts."""
    blob = " ".join(str(t).lower() for t in texts if isinstance(t, str))
    if not blob.strip():
        return []
    found = []
    for allergen, keywords in ALLERGEN_KEYWORDS.items():
        if any(kw in blob for kw in keywords):
            found.append(allergen)
    return sorted(found)


def estimate_eco_metrics(category, eco_grade):
    base_co2, base_water = CATEGORY_FOOTPRINT.get(category, CATEGORY_FOOTPRINT["unknown"])
    mult = ECO_GRADE_MULT.get(eco_grade, 1.0)
    co2 = round(base_co2 * mult, 2)               # kg CO2e per kg product
    water = int(round(base_water * mult))         # litres per kg product
    car_km = round(co2 * CO2_TO_CAR_KM, 1)        # equivalent km driven
    return co2, water, car_km


def clean_text(v):
    if not isinstance(v, str):
        return None
    v = v.strip()
    return v if v else None


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    if not os.path.exists(csv_path):
        print(f"ERROR: CSV not found at {csv_path}")
        sys.exit(1)

    print(f"Reading {csv_path} ...")
    # Only load columns that actually exist in this particular export.
    header = pd.read_csv(csv_path, sep="\t", nrows=0)
    available = [c for c in USECOLS if c in header.columns]
    df = pd.read_csv(csv_path, sep="\t", usecols=available, low_memory=False)
    print(f"  raw rows: {len(df):,}")

    # --- Filter to products with enough real data -------------------------
    df["product_name"] = df["product_name"].apply(clean_text)
    df = df[df["product_name"].notna()]

    df["nutriscore_grade"] = df["nutriscore_grade"].astype(str).str.lower().str.strip()
    df = df[df["nutriscore_grade"].isin(VALID_GRADES)]

    df["environmental_score_grade"] = df["environmental_score_grade"].astype(str).str.lower().str.strip()
    df = df[df["environmental_score_grade"].isin(VALID_GRADES)]

    for col in REQUIRED_NUTRIENTS:
        df = df[df[col].notna()]

    print(f"  rows with name + Nutri-Score + Eco-Score + core nutrients: {len(df):,}")

    # --- Build clean product records --------------------------------------
    products = []
    for _, row in df.iterrows():
        nutr = {}
        ok = True
        for col in REQUIRED_NUTRIENTS:
            val = _to_float(row.get(col))
            if val is None:
                ok = False
                break
            # Logical sanity: a single nutrient cannot exceed 100 g per 100 g
            # (energy is kcal, handled separately).
            if col != "energy-kcal_100g" and val > 100:
                ok = False
                break
            nutr[col] = round(val, 2)
        if not ok:
            continue
        # Energy sanity clip (kcal/100g rarely above ~900).
        if nutr["energy-kcal_100g"] > 900 or nutr["energy-kcal_100g"] < 0:
            continue
        for col in OPTIONAL_NUTRIENTS:
            val = _to_float(row.get(col))
            if val is None or val < 0 or val > 100:
                val = 0.0
            nutr[col] = round(val, 2)

        category = clean_text(row.get("pnns_groups_1")) or "unknown"
        if category.lower() in ("unknown", "", "nan"):
            category = "unknown"
        subcategory = clean_text(row.get("pnns_groups_2")) or category

        eco_grade = row["environmental_score_grade"]
        co2, water, car_km = estimate_eco_metrics(category, eco_grade)

        allergens = detect_allergens(
            row.get("ingredients_text"),
            row.get("allergens"),
            row.get("traces_en"),
        )

        labels = clean_text(row.get("labels_en")) or ""
        is_organic = "organic" in labels.lower() or "bio" in labels.lower()

        code = clean_text(str(row.get("code")))
        off_url = clean_text(row.get("url")) or (
            f"https://world.openfoodfacts.org/product/{code}" if code else None
        )

        nova = _to_float(row.get("nova_group"))
        additives = _to_float(row.get("additives_n"))

        # Real ingredients text + a simple ingredient count (OFF style: "N ingredients").
        ingredients_text = clean_text(row.get("ingredients_text")) or ""
        ing_tags = clean_text(row.get("ingredients_tags")) or ""
        if ing_tags:
            ingredients_n = len([t for t in ing_tags.split(",") if t.strip()])
        elif ingredients_text:
            ingredients_n = len([s for s in ingredients_text.replace(";", ",").split(",") if s.strip()])
        else:
            ingredients_n = None

        # Real numeric Eco-Score (0-100) when present -- more accurate than the
        # grade-only mapping, and used directly as the ecology score so the
        # recommendation reflects the actual environmental data.
        env_score = _to_float(row.get("environmental_score_score"))
        environmental_score = (round(max(0.0, min(100.0, env_score)), 1)
                               if env_score is not None else None)

        products.append({
            "code": code,
            "name": row["product_name"],
            "brand": clean_text(row.get("brands")) or "",
            "category": category,
            "subcategory": subcategory,
            "countries": clean_text(row.get("countries_en")) or "",
            "origins": clean_text(row.get("origins_en")) or "",
            "image": clean_text(row.get("image_small_url")) or clean_text(row.get("image_url")) or "",
            "image_large": clean_text(row.get("image_url")) or "",
            "off_url": off_url,
            "nutriscore": row["nutriscore_grade"],
            "ecoscore": eco_grade,
            "nova": int(nova) if nova else None,
            "additives_n": int(additives) if additives is not None else None,
            "labels": labels,
            "organic": is_organic,
            "allergens": allergens,
            "ingredients_text": ingredients_text,
            "ingredients_n": ingredients_n,
            "environmental_score": environmental_score,   # real OFF Eco-Score 0-100 (or None)
            "nutrients": {
                "energy_kcal": nutr["energy-kcal_100g"],
                "fat": nutr["fat_100g"],
                "saturated_fat": nutr["saturated-fat_100g"],
                "sugars": nutr["sugars_100g"],
                "salt": nutr["salt_100g"],
                "proteins": nutr["proteins_100g"],
                "fiber": nutr["fiber_100g"],
                "sodium": nutr["sodium_100g"],
            },
            "eco_metrics": {
                "co2_kg": co2,            # estimated kg CO2e per kg product
                "water_l": water,         # estimated litres per kg product
                "car_km": car_km,         # equivalent km driven by an average car
                "estimated": True,
            },
        })

    # De-duplicate by (name, brand) keeping the first occurrence.
    seen = set()
    deduped = []
    for p in products:
        key = (p["name"].lower(), p["brand"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    products = deduped

    print(f"  final clean products: {len(products):,}")
    with_img = sum(1 for p in products if p["image"])
    print(f"  with image: {with_img:,}")

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=1)
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
