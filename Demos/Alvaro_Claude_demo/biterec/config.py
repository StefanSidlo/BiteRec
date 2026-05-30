# =============================================================================
# BiteRec — Configuration
# All column names, constants, and scoring maps live here.
# =============================================================================

# ---------------------------------------------------------------------------
# CSV candidates (tried in order until one is found)
# ---------------------------------------------------------------------------
CSV_CANDIDATES = [
    "data/openfoodfacts_20MB.csv",
    "data/en.openfoodfacts.org.products.csv",
    "data/openfoodfacts.csv",
    "data/openfoodfacts_short.csv",
]

# ---------------------------------------------------------------------------
# Columns we actually need from the 180+ column OFF export.
# Loading only these makes the 12 GB file tractable in RAM.
# ---------------------------------------------------------------------------
REQUIRED_COLS = [
    "code",
    "product_name",
    "brands",
    "categories_en",
    "countries_en",
    "image_url",

    # Nutrients (per 100 g)
    "energy-kcal_100g",
    "fat_100g",
    "saturated-fat_100g",
    "carbohydrates_100g",
    "sugars_100g",
    "fiber_100g",
    "proteins_100g",
    "salt_100g",
    "sodium_100g",

    # Scores
    "nutriscore_grade",
    "nutriscore_score",
    "ecoscore_grade",
    "ecoscore_score",

    # Eco detail
    "carbon-footprint-from-known-ingredients_product",
    "packaging_tags",
    "origins_tags",
    "manufacturing_places",

    # Allergens
    "allergens_en",
    "traces_en",

    # Labels (organic etc.)
    "labels_en",
    "labels_tags",
]

# Some column names vary across OFF export versions — fallback aliases
COL_ALIASES = {
    "energy-kcal_100g": ["energy_100g"],
    "sugars_100g": ["sugar_100g"],
    "fiber_100g": ["fibers_100g", "dietary-fiber_100g"],
    "carbon-footprint-from-known-ingredients_product": [
        "carbon-footprint_100g",
        "carbon_footprint_100g",
    ],
}

# ---------------------------------------------------------------------------
# Nutri-Score
# ---------------------------------------------------------------------------
NUTRISCORE_ORDER = {"a": 5, "b": 4, "c": 3, "d": 2, "e": 1}
NUTRISCORE_COLORS = {
    "a": "#038141",
    "b": "#85bb2f",
    "c": "#fecb02",
    "d": "#ee8100",
    "e": "#e63312",
    "unknown": "#9e9e9e",
}

# ---------------------------------------------------------------------------
# Eco-Score
# ---------------------------------------------------------------------------
ECOSCORE_ORDER = {"a": 5, "b": 4, "c": 3, "d": 2, "e": 1}
ECOSCORE_COLORS = {
    "a": "#038141",
    "b": "#85bb2f",
    "c": "#fecb02",
    "d": "#ee8100",
    "e": "#e63312",
    "unknown": "#9e9e9e",
}

# Estimated CO₂ g/100g by Eco-Score grade (illustrative proxy)
CO2_BY_ECOSCORE = {"a": 50, "b": 150, "c": 400, "d": 900, "e": 1800, "unknown": 500}

# ---------------------------------------------------------------------------
# Scoring weights & normalization bounds
# ---------------------------------------------------------------------------
# Health sub-score components
HEALTH_WEIGHTS = {
    "nutriscore": 0.50,
    "protein": 0.20,
    "sugar_penalty": 0.15,
    "salt_penalty": 0.15,
}

# Per-100g bounds for min-max normalisation
NUTRIENT_BOUNDS = {
    "proteins_100g": (0, 35),
    "sugars_100g": (0, 60),
    "salt_100g": (0, 5),
    "fat_100g": (0, 50),
    "saturated-fat_100g": (0, 30),
    "fiber_100g": (0, 15),
}

# Eco sub-score components
ECO_WEIGHTS = {
    "ecoscore": 0.60,
    "co2_penalty": 0.25,
    "organic_bonus": 0.15,
}

# ---------------------------------------------------------------------------
# Allergen keywords (mapped to display label)
# ---------------------------------------------------------------------------
COMMON_ALLERGENS = {
    "gluten": ["gluten", "wheat", "rye", "barley", "oat", "spelt", "kamut"],
    "milk": ["milk", "dairy", "lactose", "whey", "casein", "butter", "cream", "cheese"],
    "eggs": ["egg", "eggs", "albumin", "ovalbum"],
    "peanuts": ["peanut", "groundnut", "arachis"],
    "tree nuts": ["almond", "cashew", "walnut", "hazelnut", "pecan", "pistachio",
                  "macadamia", "brazil nut", "chestnut", "nut"],
    "soy": ["soy", "soya", "soybean", "tofu", "edamame"],
    "fish": ["fish", "cod", "salmon", "tuna", "anchov", "sardine", "haddock"],
    "shellfish": ["shellfish", "shrimp", "prawn", "crab", "lobster", "crayfish",
                  "scallop", "clam", "mussel", "oyster"],
    "sesame": ["sesame", "tahini"],
    "celery": ["celery", "celeriac"],
    "mustard": ["mustard"],
    "sulphites": ["sulphite", "sulfite", "sulphur dioxide", "so2"],
    "lupin": ["lupin", "lupine"],
    "molluscs": ["mollusc", "mollusk", "squid", "octopus", "snail"],
}

# ---------------------------------------------------------------------------
# CO₂ to concrete unit conversions
# ---------------------------------------------------------------------------
# Average car emits ~120 g CO₂ per km
CAR_CO2_PER_KM = 120.0

# ---------------------------------------------------------------------------
# UI defaults
# ---------------------------------------------------------------------------
DEFAULT_HEALTH_WEIGHT = 0.70   # 70 % health, 30 % eco (from user research)
MIN_PRODUCTS_FOR_RECOMMENDATION = 5
MAX_SEARCH_RESULTS = 50
