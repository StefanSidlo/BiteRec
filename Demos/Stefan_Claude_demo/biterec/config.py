"""
BiteRec — central configuration.

All column names, scoring maps and tunable constants live here so the rest of
the codebase never hard-codes a magic string or number.
"""
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
MODEL_DIR = ROOT_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

# The Open Food Facts export is tab-delimited despite the .csv extension.
# The loader looks for these candidate filenames inside data/.
CSV_CANDIDATES = [
    "openfoodfacts.csv",
    "openfoodfacts_short.csv",
    "openfoodfacts_short_30MB.csv",
    "en.openfoodfacts.org.products.csv",
]
CSV_DELIMITER = "\t"
MODEL_PATH = MODEL_DIR / "nutriscore_rf.joblib"

# --------------------------------------------------------------------------- #
# Open Food Facts column names we rely on
# --------------------------------------------------------------------------- #
COL_CODE = "code"
COL_NAME = "product_name"
COL_BRANDS = "brands"
COL_CATEGORY = "categories_en"
COL_MAIN_CATEGORY = "main_category_en"
COL_PNNS = "pnns_groups_2"
COL_ORIGINS = "origins_en"
COL_LABELS = "labels_en"
COL_COUNTRIES = "countries_en"
COL_IMAGE = "image_small_url"
COL_IMAGE_FULL = "image_url"
COL_URL = "url"
COL_INGREDIENTS = "ingredients_text"
COL_ALLERGENS = "allergens"
COL_ALLERGENS_EN = "allergens_en"
COL_TRACES = "traces_en"
COL_NUTRISCORE_GRADE = "nutriscore_grade"
COL_ECOSCORE_GRADE = "environmental_score_grade"
COL_ECOSCORE_SCORE = "environmental_score_score"
COL_NOVA = "nova_group"
COL_ADDITIVES = "additives_n"

# Nutrient columns (per 100 g). These are the ML model features, in order.
NUTRIENT_FEATURES = [
    "energy-kcal_100g",
    "sugars_100g",
    "fat_100g",
    "saturated-fat_100g",
    "proteins_100g",
    "salt_100g",
    "fiber_100g",
]

# Human-readable labels for the features (used in XAI explanations).
FEATURE_LABELS = {
    "energy-kcal_100g": "energy",
    "sugars_100g": "sugar",
    "fat_100g": "fat",
    "saturated-fat_100g": "saturated fat",
    "proteins_100g": "protein",
    "salt_100g": "salt",
    "fiber_100g": "fibre",
}

# Whether a HIGH value of a nutrient is good (+1) or bad (-1) for health.
NUTRIENT_DIRECTION = {
    "energy-kcal_100g": -1,
    "sugars_100g": -1,
    "fat_100g": -1,
    "saturated-fat_100g": -1,
    "proteins_100g": +1,
    "salt_100g": -1,
    "fiber_100g": +1,
}

# --------------------------------------------------------------------------- #
# Scoring maps  (everything is normalised so HIGHER = BETTER, range 0–100)
# --------------------------------------------------------------------------- #
NUTRI_GRADE_TO_SCORE = {"a": 100, "b": 80, "c": 60, "d": 40, "e": 20}

ECO_GRADE_TO_SCORE = {
    "a-plus": 100, "a": 90, "b": 75, "c": 60, "d": 45, "e": 30, "f": 15,
}

# Illustrative carbon footprint (kg CO2e per 100 g) derived from the Eco-Score
# grade. Open Food Facts rarely fills the raw carbon-footprint field, so we use
# the Eco-Score as a transparent proxy to produce the "concrete unit" metrics
# required by FR-08. These are estimates and are always labelled as such.
ECO_GRADE_TO_CO2 = {
    "a-plus": 0.05, "a": 0.10, "b": 0.25, "c": 0.50,
    "d": 0.90, "e": 1.50, "f": 2.50,
}
# Average passenger car emits ~0.12 kg CO2e per km (EU fleet average).
CO2_KG_PER_CAR_KM = 0.12

VALID_NUTRI_GRADES = set("abcde")
VALID_ECO_GRADES = set(ECO_GRADE_TO_SCORE.keys())

# Default health/eco split (FR-03): 70 % health / 30 % eco.
DEFAULT_HEALTH_WEIGHT = 0.70

DATA_SOURCE_NAME = "Open Food Facts"
DATA_SOURCE_URL = "https://world.openfoodfacts.org"
