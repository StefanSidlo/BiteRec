"""
BiteRec – Recommendation Engine
ML approach from off_nutriscore_01.ipynb:
  - RandomForestClassifier predicts Nutri-Score from nutritional values
  - SHAP TreeExplainer for principled XAI feature attribution
  - KNN (cosine similarity) finds similar products – same food category first
"""

import numpy as np
import pandas as pd
import shap
from sklearn.neighbors import NearestNeighbors
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from data_loader import get_allergen_keywords, product_contains_allergen
import logging

logger = logging.getLogger(__name__)

KNN_FEATURES = [
    "health_score", "eco_score",
    "energy-kcal_100g", "proteins_100g", "fat_100g",
    "saturated-fat_100g", "sugars_100g", "fiber_100g", "salt_100g",
]

RF_FEATURES = [
    "energy-kcal_100g", "sugars_100g", "fat_100g",
    "saturated-fat_100g", "proteins_100g", "salt_100g", "fiber_100g",
]

FEATURE_LABELS = {
    "energy-kcal_100g":   "energy",
    "sugars_100g":        "sugar",
    "fat_100g":           "fat",
    "saturated-fat_100g": "saturated fat",
    "proteins_100g":      "protein",
    "salt_100g":          "salt",
    "fiber_100g":         "fibre",
}


class Recommender:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.rf_model = None
        self.shap_explainer = None
        self.le = None
        self._train_rf()
        self._build_knn()

    # ── RandomForest + SHAP ──────────────────────────────────────────────────

    def _train_rf(self):
        """Train RF to predict Nutri-Score; init SHAP explainer (notebook approach)."""
        train_df = self.df[self.df["nutriscore_grade"].isin(["a","b","c","d","e"])].copy()
        if len(train_df) < 50:
            logger.warning("Not enough labelled data for RF – using heuristic XAI only.")
            return

        X = train_df[RF_FEATURES]
        y = train_df["nutriscore_grade"].str.upper()

        self.le = LabelEncoder()
        y_enc = self.le.fit_transform(y)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y_enc, test_size=0.2, random_state=42, stratify=y_enc
        )
        self.rf_model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        self.rf_model.fit(X_train, y_train)

        acc = accuracy_score(y_test, self.rf_model.predict(X_test))
        logger.info(f"RandomForest trained on {len(X_train)} products – accuracy: {acc:.1%}")
        logger.info(f"  Classes: {list(self.le.classes_)}")

        # SHAP TreeExplainer (same as notebook)
        bg = X_train.sample(min(200, len(X_train)), random_state=42)
        self.shap_explainer = shap.TreeExplainer(self.rf_model, bg)
        self.rf_feature_cols = RF_FEATURES
        logger.info("SHAP TreeExplainer ready.")

    def _get_shap_values(self, x_df: pd.DataFrame) -> np.ndarray:
        """
        Return SHAP values array shaped (n_features, n_classes).
        Handles both old SHAP (list of arrays) and new SHAP >= 0.44 (3-D ndarray).
        """
        sv = self.shap_explainer.shap_values(x_df)

        if isinstance(sv, np.ndarray):
            # New SHAP: shape (n_samples, n_features, n_classes)
            return sv[0]          # → (n_features, n_classes)
        elif isinstance(sv, list):
            # Old SHAP: list[n_classes] of (n_samples, n_features)
            # Stack into (n_features, n_classes)
            return np.column_stack([arr[0] for arr in sv])
        else:
            raise ValueError(f"Unexpected shap_values type: {type(sv)}")

    # ── KNN index ────────────────────────────────────────────────────────────

    def _build_knn(self):
        X = self.df[KNN_FEATURES].values
        self.scaler = MinMaxScaler()
        self.X_scaled = self.scaler.fit_transform(X)
        self.nn = NearestNeighbors(n_neighbors=100, metric="cosine", algorithm="brute")
        self.nn.fit(self.X_scaled)
        logger.info("KNN index built.")

    # ── Search ───────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 10) -> list:
        q = query.strip().lower()
        names = self.df["product_name"].str.lower()

        # Only rows that actually contain the query string
        mask = names.str.contains(q, na=False, regex=False)
        results = self.df[mask].copy()
        if results.empty:
            return []

        rnames = results["product_name"].str.lower()

        # Rank: 0=exact, 1=starts-with, 2=any-word-starts-with, 3=contains-elsewhere
        def rank(name):
            if name == q:
                return 0
            if name.startswith(q):
                return 1
            if any(w.startswith(q) for w in name.split()):
                return 2
            return 3

        results = results.copy()
        results["_rank"] = rnames.apply(rank)
        results["_has_eco"] = results["environmental_score_grade"].isin(
            ["a-plus","a","b","c","d","e","f"]
        )
        results = results.sort_values(["_rank", "_has_eco"], ascending=[True, False])
        return self._rows_to_dicts(results.head(top_k))

    # ── Recommend ────────────────────────────────────────────────────────────

    def recommend(self, product_idx: int, health_weight: float = 0.7,
                  eco_weight: float = 0.3, allergen_input: str = "",
                  filters: dict = None) -> dict:
        product  = self.df.iloc[product_idx]
        allergen_kws = get_allergen_keywords(allergen_input)

        # --- Candidate pool: strict pnns_groups_1 category first -----------
        group = str(product.get("pnns_groups_1", "") or "").strip()

        # ── Candidate pool: same food group, ranked by KNN similarity ────────
        # Step 1 – collect all products in the same pnns_groups_1 group
        if group and group not in ("unknown", ""):
            same_group = self.df[
                (self.df["pnns_groups_1"] == group) &
                (self.df.index != product_idx)
            ].copy()
        else:
            same_group = pd.DataFrame()

        logger.debug(f"Same-group '{group}' candidates: {len(same_group)}")

        if len(same_group) >= 5:
            # Step 2 – rank same-group products by KNN cosine distance
            # (most nutritionally similar first)
            x_q = self.X_scaled[product_idx].reshape(1, -1)
            x_grp = self.scaler.transform(same_group[KNN_FEATURES].values)
            from sklearn.metrics.pairwise import cosine_distances
            dists = cosine_distances(x_q, x_grp)[0]
            same_group = same_group.copy()
            same_group["_dist"] = dists
            same_group = same_group.sort_values("_dist")

            # Step 3 – keep the 60 most similar within the group
            candidates = same_group.head(60)
        else:
            # Not enough same-category products – fall back to plain KNN pool
            knn_cands = self._knn_candidates(product_idx)
            candidates = knn_cands[knn_cands.index != product_idx].copy()
            logger.debug(f"Falling back to KNN pool ({len(candidates)} candidates)")

        # Allergen hard constraint
        if allergen_kws:
            candidates = candidates[
                ~candidates["allergen_text"].apply(
                    lambda t: product_contains_allergen(t, allergen_kws)
                )
            ]

        # Optional filters
        if filters:
            if filters.get("high_protein"):
                candidates = candidates[candidates["proteins_100g"] >= 10]
            if filters.get("low_sugar"):
                candidates = candidates[candidates["sugars_100g"] <= 5]
            if filters.get("organic"):
                candidates = candidates[
                    candidates["labels_en"].str.contains("organic|bio", na=False, case=False)
                ]

        # Fallback: whole dataset
        if candidates.empty:
            candidates = self.df[self.df.index != product_idx].copy()
            if allergen_kws:
                candidates = candidates[
                    ~candidates["allergen_text"].apply(
                        lambda t: product_contains_allergen(t, allergen_kws)
                    )
                ]

        # ── Slider-aware selection ────────────────────────────────────────────
        # combined_score weights health vs eco according to the slider
        candidates = candidates.copy()
        candidates["combined_score"] = (
            health_weight * candidates["health_score"] +
            eco_weight    * candidates["eco_score"]
        )

        searched_health = float(product.get("health_score", 0))
        searched_eco    = float(product.get("eco_score", 0))

        # "Better for You": best combined_score among candidates that improve
        # health vs. the searched product; fall back to best health overall.
        health_improved = candidates[candidates["health_score"] > searched_health]
        if len(health_improved) == 0:
            health_improved = candidates  # no strictly better – take best available
        # Sort by combined_score so the slider actually shifts which wins
        best_health = health_improved.sort_values(
            ["combined_score", "health_score"], ascending=False
        ).iloc[0]

        # "Better for Earth": best combined_score among candidates that improve
        # eco vs. the searched product AND are a different product from best_health.
        eco_pool = candidates[candidates.index != best_health.name]
        eco_improved = eco_pool[eco_pool["eco_score"] > searched_eco]
        if len(eco_improved) == 0:
            eco_improved = eco_pool  # fall back to best eco available
        best_eco = eco_improved.sort_values(
            ["eco_score", "combined_score"], ascending=False
        ).iloc[0]

        # Final safety: ensure same food group (guards against bad OFF data)
        def same_group_fallback(pick: pd.Series, pool: pd.DataFrame,
                                sort_col: str, grp: str) -> pd.Series:
            if pick.get("pnns_groups_1", "") == grp:
                return pick
            same = pool[pool["pnns_groups_1"] == grp]
            if not same.empty:
                return same.sort_values(sort_col, ascending=False).iloc[0]
            return pick

        best_health = same_group_fallback(best_health, candidates, "health_score", group)
        best_eco    = same_group_fallback(best_eco,    candidates, "eco_score",    group)

        return {
            "searched": self._row_to_dict(product, product_idx),
            "better_for_you": {
                **self._row_to_dict(best_health, best_health.name),
                "explanation": self._explain(product, best_health, "health"),
                "shap_data":   self._shap_attribution(best_health),
            },
            "better_for_earth": {
                **self._row_to_dict(best_eco, best_eco.name),
                "explanation": self._explain(product, best_eco, "eco"),
                "shap_data":   self._shap_attribution(best_eco),
            },
        }

    def _same_category_candidates(self, product: pd.Series, exclude_idx: int) -> pd.DataFrame:
        """
        Return products in the same food category, strictly ordered:
        1. Same pnns_groups_1  (e.g. "Beverages")
        2. Same first categories_en keyword (e.g. "Colas")
        Excludes the searched product itself.
        """
        group = str(product.get("pnns_groups_1", "") or "")
        cat   = str(product.get("categories_en", "") or "")

        mask = pd.Series(False, index=self.df.index)

        if group and group not in ("", "unknown"):
            mask |= (self.df["pnns_groups_1"] == group)

        # Try matching a specific sub-category keyword from categories_en
        if cat:
            for kw in [c.strip() for c in cat.split(",") if len(c.strip()) > 3]:
                hits = self.df["categories_en"].str.contains(kw, na=False, case=False, regex=False)
                if hits.sum() > 2:   # only use if there are meaningful results
                    mask |= hits
                    break

        result = self.df[mask & (self.df.index != exclude_idx)]
        return result

    def _knn_candidates(self, product_idx: int) -> pd.DataFrame:
        x = self.X_scaled[product_idx].reshape(1, -1)
        _, indices = self.nn.kneighbors(x)
        return self.df.iloc[indices[0]]

    # ── SHAP attribution ─────────────────────────────────────────────────────

    def _shap_attribution(self, product: pd.Series) -> list:
        if self.rf_model is None or self.shap_explainer is None:
            return []
        try:
            grade = product["nutriscore_grade"].upper()
            cls_idx = list(self.le.classes_).index(grade)
            x = pd.DataFrame([product[self.rf_feature_cols]])
            sv = self._get_shap_values(x)   # (n_features, n_classes)
            attributions = sv[:, cls_idx]    # (n_features,)
            result = [
                {"feature": FEATURE_LABELS.get(f, f),
                 "value":   round(float(product[f]), 2),
                 "shap":    round(float(v), 4)}
                for f, v in zip(self.rf_feature_cols, attributions)
            ]
            result.sort(key=lambda r: abs(r["shap"]), reverse=True)
            return result[:5]
        except Exception as e:
            logger.warning(f"SHAP attribution failed: {e}")
            return []

    # ── XAI explanation ──────────────────────────────────────────────────────

    def _explain(self, base: pd.Series, alt: pd.Series, mode: str) -> str:
        """SHAP-driven explanation with heuristic fallback."""
        if self.rf_model is not None and self.shap_explainer is not None:
            try:
                return self._shap_narrative(alt, mode)
            except Exception:
                pass
        return self._delta_explain(base, alt, mode)

    def _shap_narrative(self, product: pd.Series, mode: str) -> str:
        attribution = self._shap_attribution(product)
        if not attribution:
            return self._delta_explain(product, product, mode)

        if mode == "health":
            grade    = product["nutriscore_grade"].upper()
            positives = [a for a in attribution if a["shap"] > 0]
            negatives = [a for a in attribution if a["shap"] < 0]
            parts = [f"Nutri-Score {grade}."]
            if positives:
                top  = positives[0]
                feat, val = top["feature"], top["value"]
                if feat == "protein":
                    parts.append(f"High protein ({val:.1f} g/100g) is its biggest strength.")
                elif feat == "fibre":
                    parts.append(f"Good fibre ({val:.1f} g/100g) boosts its score.")
                else:
                    parts.append(f"Low {feat} ({val:.1f} g/100g) helps its score.")
            if negatives:
                top  = negatives[0]
                feat, val = top["feature"], top["value"]
                parts.append(f"Main limiting factor: {feat} ({val:.1f} g/100g).")
            return " ".join(parts[:2])
        else:
            eco = product["environmental_score_grade"].upper()
            parts = [f"Eco-Score {eco}."]
            labels = str(product.get("labels_en",""))
            if "organic" in labels.lower() or "bio" in labels.lower():
                parts.append("Certified organic production.")
            origins = str(product.get("origins_en",""))
            if origins and origins not in ("","unknown"):
                parts.append(f"Origin: {origins}.")
            if len(parts) == 1:
                parts.append("Lower environmental footprint than the searched product.")
            return " ".join(parts[:2])

    def _delta_explain(self, base: pd.Series, alt: pd.Series, mode: str) -> str:
        if mode == "health":
            g_base = base["nutriscore_grade"].upper()
            g_alt  = alt["nutriscore_grade"].upper()
            parts  = []
            if g_alt != g_base:
                parts.append(f"Nutri-Score improves from {g_base} to {g_alt}.")
            dp = alt["proteins_100g"] - base["proteins_100g"]
            ds = alt["sugars_100g"]   - base["sugars_100g"]
            if dp > 0.5:
                parts.append(f"Contains {dp:.1f} g more protein per 100 g.")
            elif ds < -1:
                parts.append(f"Has {abs(ds):.1f} g less sugar per 100 g.")
            if not parts:
                parts.append(f"Better nutritional profile (Nutri-Score {g_alt}).")
            return " ".join(parts[:2])
        else:
            e_base = base["environmental_score_grade"].upper()
            e_alt  = alt["environmental_score_grade"].upper()
            parts  = [f"Eco-Score {e_alt}."] if e_alt != e_base else [f"Better ecological profile."]
            labels = str(alt.get("labels_en",""))
            if "organic" in labels.lower():
                parts.append("Certified organic.")
            return " ".join(parts[:2])

    # ── Serialisation ─────────────────────────────────────────────────────────

    def _row_to_dict(self, row: pd.Series, idx) -> dict:
        def safe(val):
            if isinstance(val, float) and np.isnan(val):
                return None
            return val
        return {
            "idx":              int(idx),
            "name":             row["product_name"],
            "brand":            safe(row.get("brands")) or None,
            "category":         safe(row.get("pnns_groups_1")) or None,
            "categories_en":    safe(row.get("categories_en")) or None,
            "nutriscore_grade": row["nutriscore_grade"],
            "eco_grade":        row["environmental_score_grade"],
            "health_score":     round(float(row["health_score"]), 1),
            "eco_score":        round(float(row["eco_score"]), 1),
            "energy_kcal":      round(float(row["energy-kcal_100g"]), 1) if pd.notna(row["energy-kcal_100g"]) else None,
            "proteins":         round(float(row["proteins_100g"]), 1),
            "fat":              round(float(row["fat_100g"]), 1),
            "saturated_fat":    round(float(row.get("saturated-fat_100g", np.nan)), 1) if pd.notna(row.get("saturated-fat_100g")) else None,
            "sugars":           round(float(row["sugars_100g"]), 1),
            "fiber":            round(float(row.get("fiber_100g", 0)), 1),
            "salt":             round(float(row.get("salt_100g", 0)), 1),
            "allergens":        safe(row.get("allergen_text")) or None,
            "labels":           safe(row.get("labels_en")) or None,
            "origins":          safe(row.get("origins_en")) or None,
            "url":              safe(row.get("url")) or None,
            "source":           "Open Food Facts",
        }

    def _rows_to_dicts(self, df: pd.DataFrame) -> list:
        return [self._row_to_dict(row, idx) for idx, row in df.iterrows()]
