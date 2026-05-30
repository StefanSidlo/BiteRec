# =============================================================================
# BiteRec — XAI Explainer
# Plain-language explanations (FR-06), SHAP-based attribution (notebook §5),
# and contrastive comparison tables.
# =============================================================================

import numpy as np
import pandas as pd

from .recommender import key_differences, RecommendationResult
from .scoring import co2_to_car_km, is_organic, origin_to_distance
from .config import NUTRISCORE_ORDER, ECOSCORE_ORDER


# ---------------------------------------------------------------------------
# Plain-language explanations (FR-06, max 2 sentences)
# ---------------------------------------------------------------------------

def explain_better_for_you(base: pd.Series, alt: pd.Series) -> str:
    sentences = []

    base_grade = str(base.get("nutriscore_grade", "unknown")).upper()
    alt_grade  = str(alt.get("nutriscore_grade",  "unknown")).upper()
    if (base_grade in "ABCDE" and alt_grade in "ABCDE"
            and NUTRISCORE_ORDER.get(alt_grade.lower(), 0)
                > NUTRISCORE_ORDER.get(base_grade.lower(), 0)):
        sentences.append(
            f"This product has a better Nutri-Score ({alt_grade} vs {base_grade}), "
            f"indicating a more balanced nutritional profile."
        )

    for diff in key_differences(base, alt):
        if diff["improved"]:
            direction = "more" if diff["delta_pct"] > 0 else "less"
            pct   = abs(round(diff["delta_pct"]))
            label = diff["label"]
            sentences.append(
                f"It contains {pct}% {direction} {label} per 100 g compared to the original."
            )
            break

    if not sentences:
        sentences.append(
            "This alternative has a higher overall nutritional score than the original product."
        )
    return " ".join(sentences[:2])


def explain_better_for_earth(base: pd.Series, alt: pd.Series) -> str:
    sentences = []

    base_co2 = float(base.get("co2_g_per_100g") or 0)
    alt_co2  = float(alt.get("co2_g_per_100g")  or 0)
    if base_co2 > 0 and alt_co2 > 0 and base_co2 != alt_co2:
        pct = round((1 - alt_co2 / base_co2) * 100)
        if pct > 5:
            sentences.append(
                f"Its production generates roughly {pct}% less CO₂ — "
                f"{co2_to_car_km(alt_co2)} vs {co2_to_car_km(base_co2)} for the original."
            )

    base_eco = str(base.get("ecoscore_grade", "unknown")).upper()
    alt_eco  = str(alt.get("ecoscore_grade",  "unknown")).upper()
    if (base_eco in "ABCDE" and alt_eco in "ABCDE"
            and ECOSCORE_ORDER.get(alt_eco.lower(), 0)
                > ECOSCORE_ORDER.get(base_eco.lower(), 0)):
        sentences.append(
            f"It has a better Eco-Score ({alt_eco} vs {base_eco}), "
            f"reflecting lower overall environmental impact."
        )

    if is_organic(alt) and not is_organic(base):
        sentences.append("It is certified organic, which supports soil health and biodiversity.")

    origin = origin_to_distance(alt)
    if origin and "Europe" in origin:
        sentences.append("It is produced in Europe, reducing transport emissions.")

    if not sentences:
        sentences.append(
            "This alternative has a lower overall environmental footprint than the original product."
        )
    return " ".join(sentences[:2])


def explain_win_win(base: pd.Series, alt: pd.Series) -> str:
    health_part = explain_better_for_you(base, alt)
    eco_part    = explain_better_for_earth(base, alt)
    return f"🌟 Win-win choice! {health_part} On top of that, {eco_part.lower()}"


def build_explanations(result: RecommendationResult) -> dict:
    out  = {}
    base = result.searched

    if result.better_for_you is not None:
        if result.win_win:
            out["better_for_you_text"] = explain_win_win(base, result.better_for_you)
        else:
            out["better_for_you_text"] = explain_better_for_you(base, result.better_for_you)
        out["better_for_you_diffs"] = key_differences(base, result.better_for_you)

    if result.better_for_earth is not None and not result.win_win:
        out["better_for_earth_text"] = explain_better_for_earth(base, result.better_for_earth)
        out["better_for_earth_diffs"] = key_differences(base, result.better_for_earth)

    return out


# ---------------------------------------------------------------------------
# SHAP-based attribution helpers (for AI Details tab)
# ---------------------------------------------------------------------------

def shap_waterfall_df(shap_data: dict, target_class: str = "A", sample_idx: int = 0) -> pd.DataFrame:
    """
    Build a tidy DataFrame for a Plotly waterfall plot from SHAP data.

    shap_data["values"] shape:
      - Local (single row):  (n_features, n_classes)
      - Summary (n rows):    (n_samples, n_features, n_classes)

    target_class : the grade to explain (default 'A')
    sample_idx   : row index for summary data (ignored for local data)
    """
    if not shap_data:
        return pd.DataFrame()

    classes       = shap_data.get("classes", [])
    classes_upper = [str(c).upper() for c in classes]
    target_upper  = target_class.upper()
    if target_upper not in classes_upper:
        target_upper = classes_upper[0] if classes_upper else "A"
    class_idx = classes_upper.index(target_upper)

    sv = np.array(shap_data["values"])  # could be (n_feat, n_cls) or (n_samples, n_feat, n_cls)

    if sv.ndim == 3:
        # Summary shape: pick the requested sample
        sv = sv[sample_idx]          # → (n_features, n_classes)
    # Now sv is (n_features, n_classes)
    sv_for_class = sv[:, class_idx]  # → (n_features,)

    features    = shap_data["features"]
    data_values = shap_data["data"]

    # Ensure lengths match
    n = min(len(features), len(sv_for_class), len(data_values))

    df = pd.DataFrame({
        "feature":    features[:n],
        "value":      data_values[:n],
        "shap_value": sv_for_class[:n],
    })
    df["direction"] = df["shap_value"].apply(lambda x: "positive" if x >= 0 else "negative")
    df["abs_shap"]  = df["shap_value"].abs()
    df = df.sort_values("abs_shap", ascending=True).drop(columns="abs_shap")

    df["feature_label"] = (
        df["feature"]
        .str.replace("_100g", " /100g")
        .str.replace("-", " ")
        .str.replace("energy kcal /100g", "Energy (kcal/100g)")
    )
    df["value_label"] = df["value"].round(2).astype(str) + " g"
    energy_mask = df["feature"] == "energy-kcal_100g"
    df.loc[energy_mask, "value_label"] = (
        df.loc[energy_mask, "value"].round(0).astype(int).astype(str) + " kcal"
    )
    return df


def shap_global_importance_df(shap_data: dict) -> pd.DataFrame:
    """
    Compute mean(|SHAP|) per feature across all classes — global importance.
    shap_data["values"] shape: (n_samples, n_features, n_classes)
    Returns DataFrame with [feature, importance].
    """
    if not shap_data or "values" not in shap_data:
        return pd.DataFrame()

    sv       = np.array(shap_data["values"])  # (n_samples, n_features, n_classes)
    features = shap_data["features"]

    if sv.ndim == 3:
        mean_abs = np.abs(sv).mean(axis=(0, 2))   # mean over samples and classes → (n_features,)
    elif sv.ndim == 2:
        mean_abs = np.abs(sv).mean(axis=0)         # (n_features,)
    else:
        return pd.DataFrame()

    n = min(len(features), len(mean_abs))
    df = pd.DataFrame({"feature": features[:n], "importance": mean_abs[:n]})
    df["feature_label"] = (
        df["feature"]
        .str.replace("_100g", " /100g")
        .str.replace("-", " ")
    )
    return df.sort_values("importance", ascending=False)


# ---------------------------------------------------------------------------
# Nutrient attribution table (simple, no SHAP required)
# ---------------------------------------------------------------------------

def nutrient_attribution(row: pd.Series, median_row: pd.Series) -> pd.DataFrame:
    """
    Classify each nutrient as 'helps' or 'hurts' vs. the dataset median.
    Used as a lightweight fallback when SHAP is unavailable.
    """
    checks = [
        ("proteins_100g",      "Protein",       True),
        ("fiber_100g",         "Fibre",          True),
        ("sugars_100g",        "Sugar",          False),
        ("salt_100g",          "Salt",           False),
        ("saturated-fat_100g", "Saturated Fat",  False),
        ("fat_100g",           "Total Fat",      False),
        ("energy-kcal_100g",   "Calories",       False),
    ]
    records = []
    for col, label, higher_is_better in checks:
        val = row.get(col)
        med = median_row.get(col)
        if pd.isna(val) or pd.isna(med):
            continue
        val, med = float(val), float(med)
        direction = "helps" if (val >= med) == higher_is_better else "hurts"
        records.append({
            "Nutrient":               label,
            "This product (per 100g)": round(val, 2),
            "Dataset median":          round(med, 2),
            "Effect": "✅ Helps score" if direction == "helps" else "⚠️ Hurts score",
        })
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Contrastive comparison table
# ---------------------------------------------------------------------------

def contrastive_table(base: pd.Series, alt: pd.Series, alt_label: str) -> pd.DataFrame:
    cols = [
        ("nutriscore_grade",      "Nutri-Score",         None),
        ("ecoscore_grade",        "Eco-Score",            None),
        ("energy-kcal_100g",      "Energy (kcal/100g)",   False),
        ("proteins_100g",         "Protein (g/100g)",     True),
        ("sugars_100g",           "Sugar (g/100g)",       False),
        ("salt_100g",             "Salt (g/100g)",        False),
        ("fat_100g",              "Fat (g/100g)",         False),
        ("fiber_100g",            "Fibre (g/100g)",       True),
        ("co2_g_per_100g",        "CO₂ (g/100g, est.)",  False),
    ]
    records = []
    for col, label, higher_is_better in cols:
        bv_raw = base.get(col, "—")
        av_raw = alt.get(col,  "—")

        if col in ("nutriscore_grade", "ecoscore_grade"):
            bv = str(bv_raw).upper() if str(bv_raw) not in ("nan", "unknown", "") else "—"
            av = str(av_raw).upper() if str(av_raw) not in ("nan", "unknown", "") else "—"
            order  = NUTRISCORE_ORDER if "nutri" in col else ECOSCORE_ORDER
            b_score = order.get(str(bv_raw).lower(), 0)
            a_score = order.get(str(av_raw).lower(), 0)
            winner = alt_label if a_score > b_score else ("Original" if b_score > a_score else "—")
        else:
            try:
                bv = round(float(bv_raw), 2) if not pd.isna(bv_raw) else "—"
                av = round(float(av_raw), 2) if not pd.isna(av_raw) else "—"
            except (ValueError, TypeError):
                bv, av = "—", "—"
            if isinstance(bv, float) and isinstance(av, float) and higher_is_better is not None:
                winner = alt_label if (av > bv) == higher_is_better and av != bv else (
                    "Original" if (bv > av) == higher_is_better and av != bv else "—"
                )
            else:
                winner = "—"

        records.append({"Attribute": label, "Original": bv, alt_label: av, "Better": winner})

    return pd.DataFrame(records)
