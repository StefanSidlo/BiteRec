"""
BiteRec — Explainable AI layer (FR-06, XAI requirement of the assignment).

Generates:
  - plain-language explanations (max 2 sentences) for why an alternative beats
    the searched product, referencing concrete attributes and eco units;
  - local feature attribution: which nutrients pulled the Nutri-Score up/down,
    weighted by the RandomForest's global feature importance;
  - contrastive ("why not B?") deltas between two products.

Framing follows NFR-04: improvements are always phrased as GAINS, never as
sacrifices or guilt.
"""
from __future__ import annotations

import pandas as pd

from . import config as C
from . import scoring


# --------------------------------------------------------------------------- #
# Local feature attribution (uses the trained model's importances)
# --------------------------------------------------------------------------- #
def feature_attribution(row: pd.Series, model) -> list[dict]:
    """Per-nutrient contribution to this product's Nutri-Score.

    For each nutrient we compare the product's value to the dataset median and
    weight the gap by (a) the model's global feature importance and (b) whether
    a high value is good or bad for health. Positive = helps the score.
    """
    importance = model.feature_importance
    out = []
    for feat in C.NUTRIENT_FEATURES:
        val = row.get(feat)
        if pd.isna(val):
            continue
        median = model.medians.get(feat, 0) or 0
        spread = abs(median) + 1e-6
        gap = (float(val) - median) / spread          # >0 means above median
        direction = C.NUTRIENT_DIRECTION[feat]         # +1 good-high, -1 good-low
        contribution = gap * direction * importance.get(feat, 0)
        out.append({
            "feature": feat,
            "label": C.FEATURE_LABELS[feat],
            "value": round(float(val), 1),
            "importance": round(importance.get(feat, 0), 3),
            "contribution": round(contribution, 4),
        })
    out.sort(key=lambda d: abs(d["contribution"]), reverse=True)
    return out


# --------------------------------------------------------------------------- #
# Plain-language explanation for an alternative
# --------------------------------------------------------------------------- #
def _fmt_pct(a: float, b: float) -> str | None:
    """Percentage reduction from b to a (only if a meaningfully lower)."""
    if pd.isna(a) or pd.isna(b) or b <= 0 or a >= b:
        return None
    return f"{round(100 * (b - a) / b)}%"


def explain_alternative(alt: pd.Series, base: pd.Series, kind: str) -> str:
    """One/two-sentence, gain-framed reason this alternative was recommended."""
    name = alt.get(C.COL_NAME, "This product")
    reasons = []

    if kind == "health":
        ag, bg = alt.get("effective_grade", ""), base.get("effective_grade", "")
        if ag and bg and ag < bg:  # 'a' < 'b' lexicographically => better grade
            reasons.append(f"a better Nutri-Score ({ag.upper()} vs {bg.upper()})")
        red = _fmt_pct(alt.get("sugars_100g"), base.get("sugars_100g"))
        if red:
            reasons.append(f"{red} less sugar")
        if pd.notna(alt.get("proteins_100g")) and pd.notna(base.get("proteins_100g")) \
                and alt["proteins_100g"] > base["proteins_100g"]:
            reasons.append(
                f"more protein ({alt['proteins_100g']:.0f} g vs "
                f"{base['proteins_100g']:.0f} g per 100 g)"
            )

    else:  # eco
        ag, bg = alt.get(C.COL_ECOSCORE_GRADE, ""), base.get(C.COL_ECOSCORE_GRADE, "")
        if ag and bg and scoring._grade_score(ag, C.ECO_GRADE_TO_SCORE) > \
                scoring._grade_score(bg, C.ECO_GRADE_TO_SCORE):
            reasons.append(f"a stronger Eco-Score ({ag.upper()} vs {bg.upper()})")
        a_co2 = scoring.estimate_co2_per_100g(alt)
        b_co2 = scoring.estimate_co2_per_100g(base)
        if a_co2 is not None and b_co2 is not None and a_co2 < b_co2:
            saved_km = round(scoring.co2_to_car_km(b_co2 - a_co2), 1)
            reasons.append(
                f"a lower estimated carbon footprint "
                f"(about {saved_km} km of car driving saved per 100 g)"
            )

    if not reasons:
        # Fallback gain framing.
        if kind == "health":
            reasons.append("a higher overall nutritional score")
        else:
            reasons.append("a lighter overall environmental footprint")

    lead = "Better for You" if kind == "health" else "Better for Earth"
    body = reasons[0] if len(reasons) == 1 else \
        ", ".join(reasons[:-1]) + f" and {reasons[-1]}"
    return f"{lead}: {name} offers {body}."


# --------------------------------------------------------------------------- #
# Contrastive explanation ("Why not B?")
# --------------------------------------------------------------------------- #
def contrast(a: pd.Series, b: pd.Series) -> list[dict]:
    """Dimension-by-dimension delta between two products (a = recommended)."""
    rows = []

    def add(dim, va, vb, higher_better=True, unit=""):
        if pd.isna(va) and pd.isna(vb):
            return
        va = None if pd.isna(va) else round(float(va), 1)
        vb = None if pd.isna(vb) else round(float(vb), 1)
        winner = "—"
        if va is not None and vb is not None:
            if va == vb:
                winner = "tie"
            else:
                a_wins = (va > vb) if higher_better else (va < vb)
                winner = "recommended" if a_wins else "yours"
        rows.append({"dimension": dim, "recommended": va, "yours": vb,
                     "unit": unit, "favours": winner})

    add("Health score", a.get("health_score"), b.get("health_score"))
    add("Eco score", a.get("eco_score"), b.get("eco_score"))
    add("Protein", a.get("proteins_100g"), b.get("proteins_100g"), True, "g/100g")
    add("Sugar", a.get("sugars_100g"), b.get("sugars_100g"), False, "g/100g")
    add("Salt", a.get("salt_100g"), b.get("salt_100g"), False, "g/100g")
    add("Est. CO\u2082", scoring.estimate_co2_per_100g(a),
        scoring.estimate_co2_per_100g(b), False, "kg/100g")
    return rows
