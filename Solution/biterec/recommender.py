"""
recommender.py  --  BiteRec recommendation + ML engine
========================================================

Loads the clean product catalog (data/products.json) and provides:

  * a RandomForest Nutri-Score model (same approach as the project's ML
    notebook) used to derive a *continuous* health score and to power the
    local XAI feature-attribution explanations;
  * a continuous eco score from the Eco-Score grade;
  * search + autocomplete;
  * the "Alternative Engine": for any product it returns a "Better for You"
    (nutrition) and a "Better for Earth" (ecology) alternative, plus an
    optional primary pick that beats the original on both dimensions;
  * allergen hard-filtering (applied before any scoring);
  * radar-chart data across several dimensions;
  * plain-language + contrastive explanations (FR-06).

All scores are 0-100 where higher is always better, so they are safe to feed
straight into the radar charts and the priority slider.
"""

import os
import json
import math
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

try:
    import shap
    _HAS_SHAP = True
except Exception:  # pragma: no cover - shap is listed in requirements
    _HAS_SHAP = False

HERE = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_JSON = os.path.join(HERE, "data", "products.json")

# Grade -> anchor value used for continuous scores (A best ... E worst).
GRADE_VALUE = {"a": 5, "b": 4, "c": 3, "d": 2, "e": 1}
NUTRIENT_KEYS = ["energy_kcal", "fat", "saturated_fat", "sugars",
                 "salt", "proteins", "fiber", "sodium"]
# Features fed to the ML model (mirrors the project's notebook).
ML_FEATURES = ["energy_kcal", "sugars", "fat", "saturated_fat",
               "proteins", "salt", "fiber"]

# Human-friendly labels for explanations.
NUTRIENT_LABEL = {
    "energy_kcal": "energy", "fat": "fat", "saturated_fat": "saturated fat",
    "sugars": "sugar", "salt": "salt", "proteins": "protein",
    "fiber": "fibre", "sodium": "sodium",
}
# Nutrients where MORE is better (the rest are "less is better").
HIGHER_IS_BETTER = {"proteins", "fiber"}


def _grade_to_score(grade):
    """Map an a-e grade to a 0-100 score (A=90 ... E=18)."""
    return {"a": 90, "b": 72, "c": 54, "d": 36, "e": 18}.get(grade, 50)


class Recommender:
    def __init__(self, path=PRODUCTS_JSON):
        with open(path, "r", encoding="utf-8") as f:
            self.products = json.load(f)
        # Give every product a stable integer id.
        for i, p in enumerate(self.products):
            p["id"] = i
        self.by_id = {p["id"]: p for p in self.products}

        self._train_model()
        self._train_eco_model()
        self._compute_catalog_stats()
        self._score_all()

    # ------------------------------------------------------------------ ML
    def _train_model(self):
        """Train a RandomForest to predict the Nutri-Score grade from nutrients.

        This mirrors the team's ML notebook. We use the model two ways:
          1. predict_proba gives a smooth, continuous health score; and
          2. a local perturbation analysis gives per-nutrient attributions
             for the XAI explanations.
        """
        X, y = [], []
        for p in self.products:
            X.append([p["nutrients"][k] for k in ML_FEATURES])
            y.append(p["nutriscore"])
        self.X = np.array(X, dtype=float)
        self.y = np.array(y)
        self.model = RandomForestClassifier(n_estimators=120, random_state=42)
        self.model.fit(self.X, self.y)
        self.classes_ = list(self.model.classes_)
        # class index -> grade value, for the expected-value calculation
        self._class_values = np.array([GRADE_VALUE.get(c, 3) for c in self.classes_])
        # class index -> health on a 0-100 scale (A=100 ... E=0), used to turn
        # SHAP's per-class contributions into a single, readable health axis.
        self._class_health = np.array(
            [(GRADE_VALUE.get(c, 3) - 1) / 4 * 100 for c in self.classes_])
        # SHAP TreeExplainer -- the "gold standard" local explanation used in
        # the project notebook. We collapse its per-class output onto the
        # health axis to build a readable waterfall (see shap_attribution).
        self.explainer = None
        self.shap_importance = {}
        if _HAS_SHAP:
            try:
                self.explainer = shap.TreeExplainer(self.model)
                self._shap_base = float(np.array(self.explainer.expected_value)
                                        @ self._class_health)
                # Global SHAP importance: mean |SHAP| per feature across the
                # catalog, summed over classes (matches the notebook's
                # summary_plot(plot_type="bar")).
                sv = np.array(self.explainer.shap_values(self.X))   # (n, feat, cls)
                mean_abs = np.abs(sv).sum(axis=2).mean(axis=0)       # (feat,)
                self.shap_importance = {ML_FEATURES[i]: float(mean_abs[i])
                                        for i in range(len(ML_FEATURES))}
            except Exception:
                self.explainer = None
                self.shap_importance = {}
        # feature importances, normalised
        imp = self.model.feature_importances_
        self.feature_importance = {ML_FEATURES[i]: float(imp[i]) for i in range(len(ML_FEATURES))}
        # 5-fold cross-validated accuracy -- an honest estimate of how well
        # the model generalises, surfaced on the insights dashboard.
        try:
            cv = cross_val_score(
                RandomForestClassifier(n_estimators=120, random_state=42),
                self.X, self.y, cv=5)
            self.train_accuracy = float(cv.mean())
        except Exception:
            self.train_accuracy = float((self.model.predict(self.X) == self.y).mean())

    def _expected_health(self, feature_vector):
        """Continuous health score 0-100 from the model's class probabilities."""
        proba = self.model.predict_proba([feature_vector])[0]
        expected = float(np.dot(proba, self._class_values))  # 1..5
        return round((expected - 1) / 4 * 100, 1)            # -> 0..100

    # -------------------------------------------------------- catalog stats
    def _compute_catalog_stats(self):
        arr = {k: np.array([p["nutrients"][k] for p in self.products]) for k in NUTRIENT_KEYS}
        self.medians = {k: float(np.median(v)) for k, v in arr.items()}
        self.maxes = {k: float(np.percentile(v, 95)) or 1.0 for k, v in arr.items()}
        self.co2_max = float(np.percentile([p["eco_metrics"]["co2_kg"] for p in self.products], 95)) or 1.0
        self.water_max = float(np.percentile([p["eco_metrics"]["water_l"] for p in self.products], 95)) or 1.0
        # Per-category nutrient medians, for fair, like-for-like explanations.
        self.cat_medians = {}
        for p in self.products:
            self.cat_medians.setdefault(p["category"], {k: [] for k in NUTRIENT_KEYS})
            for k in NUTRIENT_KEYS:
                self.cat_medians[p["category"]][k].append(p["nutrients"][k])
        for cat, d in self.cat_medians.items():
            self.cat_medians[cat] = {k: float(np.median(v)) for k, v in d.items()}

    # --------------------------------------------------------------- scoring
    def _score_all(self):
        for p in self.products:
            fv = [p["nutrients"][k] for k in ML_FEATURES]
            p["health_score"] = self._expected_health(fv)
            # Prefer the real Open Food Facts environmental score (0-100); fall
            # back to the grade mapping only when the numeric value is missing.
            env = p.get("environmental_score")
            p["eco_score"] = round(float(env), 1) if env is not None else _grade_to_score(p["ecoscore"])
        # Radar dimensions need normalised 0-100 (higher = better) values.
        for p in self.products:
            p["radar"] = self._radar_dims(p)

    def combined_score(self, p, w_health):
        return round(w_health * p["health_score"] + (1 - w_health) * p["eco_score"], 1)

    def _radar_dims(self, p):
        n = p["nutrients"]
        def norm(val, mx):  # less is better
            return round(max(0, 100 - min(100, val / mx * 100)), 1)
        def normhi(val, mx):  # more is better
            return round(min(100, val / mx * 100), 1)
        return {
            "Nutrition": p["health_score"],
            "Eco": p["eco_score"],
            "Protein": normhi(n["proteins"], self.maxes["proteins"]),
            "Low sugar": norm(n["sugars"], self.maxes["sugars"]),
            "Low salt": norm(n["salt"], self.maxes["salt"]),
            "Low CO\u2082": norm(p["eco_metrics"]["co2_kg"], self.co2_max),
        }

    def nutrition_radar(self, p):
        n = p["nutrients"]
        def norm(val, mx):
            return round(max(0, 100 - min(100, val / mx * 100)), 1)
        def normhi(val, mx):
            return round(min(100, val / mx * 100), 1)
        return {
            "Protein": normhi(n["proteins"], self.maxes["proteins"]),
            "Fibre": normhi(n["fiber"], self.maxes["fiber"]),
            "Low sugar": norm(n["sugars"], self.maxes["sugars"]),
            "Low sat. fat": norm(n["saturated_fat"], self.maxes["saturated_fat"]),
            "Low salt": norm(n["salt"], self.maxes["salt"]),
            "Low energy": norm(n["energy_kcal"], self.maxes["energy_kcal"]),
        }

    def eco_radar(self, p):
        em = p["eco_metrics"]
        def norm(val, mx):
            return round(max(0, 100 - min(100, val / mx * 100)), 1)
        return {
            "Eco-Score": p["eco_score"],
            "Low CO\u2082": norm(em["co2_kg"], self.co2_max),
            "Low water": norm(em["water_l"], self.water_max),
            "Organic": 100.0 if p["organic"] else 25.0,
            "Few additives": 100.0 if (p.get("additives_n") in (0, None)) else max(0, 100 - p["additives_n"] * 20),
            "Local": 80.0 if p["origins"] else 45.0,
        }

    # ---------------------------------------------------------------- search
    def search(self, query, limit=20):
        q = (query or "").strip().lower()
        if not q:
            return []
        scored = []
        for p in self.products:
            hay = (p["name"] + " " + p["brand"]).lower()
            if q in hay:
                # rank: exact-start > word-start > contains
                name = p["name"].lower()
                if name.startswith(q):
                    rank = 0
                elif any(w.startswith(q) for w in name.split()):
                    rank = 1
                else:
                    rank = 2
                scored.append((rank, p))
        scored.sort(key=lambda t: (t[0], t[1]["name"].lower()))
        return [self.public(p) for _, p in scored[:limit]]

    def suggest(self, query, limit=8):
        q = (query or "").strip().lower()
        if not q:
            return []
        out, seen = [], set()
        # prioritise name-prefix matches, then contains
        for phase in (0, 1):
            for p in self.products:
                name = p["name"].lower()
                hit = name.startswith(q) if phase == 0 else (q in name)
                if hit and p["name"] not in seen:
                    seen.add(p["name"])
                    out.append({
                        "id": p["id"], "name": p["name"], "brand": p["brand"],
                        "image": p["image"], "nutriscore": p["nutriscore"],
                        "ecoscore": p["ecoscore"], "category": p["category"],
                    })
                if len(out) >= limit:
                    return out
        return out

    # -------------------------------------------------------- recommendation
    def _allergen_ok(self, p, allergens):
        if not allergens:
            return True
        return not (set(p["allergens"]) & set(allergens))

    @staticmethod
    def _passes_filters(p, f):
        """Soft nutrition/ecology filters, shared by search results and the
        recommendation pool so a filter change updates BOTH live. `f` is a dict
        of optional constraints (checkboxes + numeric slider thresholds)."""
        if not f:
            return True
        n = p["nutrients"]
        # checkbox presets
        if f.get("high_protein") and n["proteins"] < 8: return False
        if f.get("low_sugar") and n["sugars"] > 5: return False
        if f.get("low_salt") and n["salt"] > 0.3: return False
        if f.get("low_satfat") and n["saturated_fat"] > 3: return False
        if f.get("high_fibre") and n["fiber"] < 3: return False
        if f.get("low_calorie") and n["energy_kcal"] > 150: return False
        if f.get("low_co2") and p["eco_metrics"]["co2_kg"] > 2: return False
        if f.get("organic") and not p["organic"]: return False
        if f.get("few_additives") and not (p.get("additives_n") == 0
                                           or (p.get("nova") and p["nova"] <= 2)): return False
        # numeric sliders (only applied when present / not at the "off" extreme)
        order = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
        if f.get("minNutri") and order.get(p["nutriscore"], 9) > order.get(f["minNutri"], 9): return False
        if f.get("minEco") and order.get(p["ecoscore"], 9) > order.get(f["minEco"], 9): return False
        if f.get("max_sugar") is not None and n["sugars"] > f["max_sugar"]: return False
        if f.get("min_protein") is not None and n["proteins"] < f["min_protein"]: return False
        if f.get("max_salt") is not None and n["salt"] > f["max_salt"]: return False
        if f.get("max_satfat") is not None and n["saturated_fat"] > f["max_satfat"]: return False
        if f.get("max_energy") is not None and n["energy_kcal"] > f["max_energy"]: return False
        if f.get("min_fibre") is not None and n["fiber"] < f["min_fibre"]: return False
        return True

    def recommend(self, product_id, w_health=0.7, allergens=None,
                  show_health=True, show_eco=True, filters=None):
        allergens = allergens or []
        base = self.by_id.get(product_id)
        if base is None:
            return None
        # If the user disabled both, fall back to showing both.
        if not show_health and not show_eco:
            show_health = show_eco = True

        # Candidate pool: prefer same sub-category, then same category, then
        # any product (FR: same-category preference). Always allergen-safe and
        # never the base product itself. The locality is chosen first, THEN the
        # user's nutrition/ecology filters are applied -- so the alternatives
        # stay in the same food category AND respect the live filters.
        def locality(predicate):
            return [p for p in self.products
                    if p["id"] != base["id"] and predicate(p)
                    and self._allergen_ok(p, allergens)]

        loc = locality(lambda p: p["subcategory"] == base["subcategory"])
        if len(loc) < 2:
            loc = locality(lambda p: p["category"] == base["category"])
        if len(loc) < 2:
            loc = locality(lambda p: True)

        pool = [p for p in loc if self._passes_filters(p, filters)]

        for p in pool:
            p["_combined"] = self.combined_score(p, w_health)
        base["_combined"] = self.combined_score(base, w_health)

        def card(p, kind, rank=None):
            if p is None:
                return None
            c = {
                **self.public(p),
                "kind": kind,
                "combined": p["_combined"],
                "explanation": self._explain(p, base, kind),
                "contrastive": self._contrastive(p, base),
                "radar": p["radar"],
            }
            if rank is not None:
                c["rank"] = rank
            return c

        alternatives = []
        unavailable = []   # goals with no genuinely-better option in this category
        if show_health and show_eco:
            # One genuinely healthier + one genuinely greener (distinct products).
            healthier = [p for p in pool if p["health_score"] > base["health_score"]]
            by = max(healthier, key=lambda p: (p["health_score"], p["_combined"])) if healthier else None
            greener = [p for p in pool if p["eco_score"] > base["eco_score"] and (not by or p["id"] != by["id"])]
            be = max(greener, key=lambda p: (p["eco_score"], p["_combined"])) if greener else None
            if by: alternatives.append(card(by, "Better for You"))
            else: unavailable.append("health")
            if be: alternatives.append(card(be, "Better for Earth"))
            elif not [p for p in pool if p["eco_score"] > base["eco_score"]]:
                unavailable.append("eco")
        elif show_health:
            ranked = sorted([p for p in pool if p["health_score"] > base["health_score"]],
                            key=lambda p: (p["health_score"], p["_combined"]), reverse=True)[:3]
            alternatives = [card(p, "Better for You", rank=i + 1) for i, p in enumerate(ranked)]
            if not ranked: unavailable.append("health")
        else:
            ranked = sorted([p for p in pool if p["eco_score"] > base["eco_score"]],
                            key=lambda p: (p["eco_score"], p["_combined"]), reverse=True)[:3]
            alternatives = [card(p, "Better for Earth", rank=i + 1) for i, p in enumerate(ranked)]
            if not ranked: unavailable.append("eco")

        return {
            "base": {
                **self.public(base),
                "combined": base["_combined"],
                "radar": base["radar"],
                "attribution": self._attribution(base),
                "shap": self.shap_attribution(base),
                "shap_grades": self.shap_grades(base),
            },
            "alternatives": [a for a in alternatives if a],
            "unavailable": unavailable,
            "mode": ("both" if show_health and show_eco else
                     "health" if show_health else "eco"),
            "weights": {"health": round(w_health, 2), "eco": round(1 - w_health, 2)},
        }

    # ----------------------------------------------------------------- XAI
    def _attribution(self, p):
        """Local feature attribution: how far is each nutrient pushing the
        health score, relative to the typical product in its category?
        Returns a list ordered by impact, for the 'why this grade' panel."""
        base_fv = [p["nutrients"][k] for k in ML_FEATURES]
        base_health = self._expected_health(base_fv)
        cat_med = self.cat_medians.get(p["category"], self.medians)
        out = []
        for i, k in enumerate(ML_FEATURES):
            fv = list(base_fv)
            fv[i] = cat_med.get(k, self.medians[k])  # neutralise this nutrient
            delta = base_health - self._expected_health(fv)
            out.append({
                "feature": NUTRIENT_LABEL[k],
                "key": k,
                "value": p["nutrients"][k],
                "typical": round(cat_med.get(k, self.medians[k]), 1),
                "impact": round(delta, 1),          # +ve helps health, -ve hurts
                "importance": round(self.feature_importance.get(k, 0), 3),
            })
        out.sort(key=lambda d: abs(d["impact"]), reverse=True)
        return out

    def shap_attribution(self, p):
        """SHAP-based 'why this grade?' explanation, mirroring the project
        notebook's waterfall plot.

        TreeExplainer gives a contribution for every (feature, class) pair.
        We project those onto a single 0-100 health axis (A=100 ... E=0), so
        the result reads as a waterfall: start at the average product, each
        nutrient nudges the score up (green) or down (red), and you land on
        this product's predicted health score. The decomposition is exact:
        base + sum(contributions) == predicted health.
        """
        fv = np.array([[p["nutrients"][k] for k in ML_FEATURES]], dtype=float)
        predicted = self._expected_health(fv[0])
        if self.explainer is None:
            # graceful fallback to the perturbation attribution
            attr = self._attribution(p)
            return {
                "available": False,
                "base": 50.0,
                "predicted": predicted,
                "grade": p["nutriscore"].upper(),
                "features": [{"feature": a["feature"], "key": a["key"],
                              "value": a["value"], "contribution": a["impact"]}
                             for a in attr],
            }
        sv = np.array(self.explainer.shap_values(fv))[0]      # (features, classes)
        contrib = (sv * self._class_health).sum(axis=1)       # (features,)
        feats = []
        for i, k in enumerate(ML_FEATURES):
            feats.append({
                "feature": NUTRIENT_LABEL[k],
                "key": k,
                "value": round(p["nutrients"][k], 1),
                "unit": "kcal" if k == "energy_kcal" else "g",
                "contribution": round(float(contrib[i]), 1),  # +health / -health
            })
        feats.sort(key=lambda d: abs(d["contribution"]), reverse=True)
        return {
            "available": True,
            "base": round(self._shap_base, 1),       # avg product health
            "predicted": predicted,                  # this product's health
            "grade": p["nutriscore"].upper(),
            "features": feats,
        }

    def _train_eco_model(self):
        """A second Random Forest that learns which *product attributes* are
        associated with the Eco-Score grade in this dataset (food category,
        organic label, processing level, additive count).

        This is an honest, learned approximation: the official Open Food Facts
        Eco-Score also uses packaging and transport data that this export does
        not contain, so the model is presented as 'what is associated with the
        grade here', and explained with the same SHAP method as the health model.
        """
        self.eco_model = None
        self.eco_explainer = None
        self.eco_feature_importance = {}
        try:
            cats = sorted(set(p["category"] for p in self.products))
            self.eco_categories = cats
            nova_vals = [p["nova"] for p in self.products if p.get("nova")]
            add_vals = [p["additives_n"] for p in self.products if p.get("additives_n") is not None]
            self._nova_med = float(np.median(nova_vals)) if nova_vals else 4.0
            self._add_med = float(np.median(add_vals)) if add_vals else 0.0

            def feat(p):
                row = [1.0 if p["category"] == c else 0.0 for c in cats]
                row.append(1.0 if p.get("organic") else 0.0)
                row.append(float(p["nova"]) if p.get("nova") else self._nova_med)
                row.append(float(p["additives_n"]) if p.get("additives_n") is not None else self._add_med)
                return row

            self._eco_feat = feat
            Xe = np.array([feat(p) for p in self.products], dtype=float)
            ye = np.array([p["ecoscore"] for p in self.products])
            self.eco_model = RandomForestClassifier(n_estimators=120, random_state=42)
            self.eco_model.fit(Xe, ye)
            self.eco_classes_ = list(self.eco_model.classes_)
            self._eco_class_score = np.array(
                [(GRADE_VALUE.get(c, 3) - 1) / 4 * 100 for c in self.eco_classes_])
            self._n_cat = len(cats)
            # readable names for the non-category features
            self._eco_tail_names = ["Organic label", "Processing (NOVA group)", "Additives (count)"]
            # global importance (group the category one-hots into one bucket)
            imp = self.eco_model.feature_importances_
            cat_imp = float(imp[:self._n_cat].sum())
            self.eco_feature_importance = {
                "Food category": round(cat_imp, 3),
                "Organic label": round(float(imp[self._n_cat]), 3),
                "Processing (NOVA)": round(float(imp[self._n_cat + 1]), 3),
                "Additives": round(float(imp[self._n_cat + 2]), 3),
            }
            if _HAS_SHAP:
                self.eco_explainer = shap.TreeExplainer(self.eco_model)
                self._eco_shap_base = float(np.array(self.eco_explainer.expected_value)
                                            @ self._eco_class_score)
            try:
                self.eco_accuracy = round(float(
                    cross_val_score(RandomForestClassifier(n_estimators=80, random_state=1),
                                    Xe, ye, cv=5).mean()) * 100, 1)
            except Exception:
                self.eco_accuracy = None
        except Exception:
            self.eco_model = None

    def eco_attribution(self, p):
        """SHAP 'why this Eco-Score?' on a 0-100 ecology axis, with the food
        category one-hots aggregated into a single readable contribution."""
        grade = p["ecoscore"].upper()
        if self.eco_model is None:
            return {"available": False, "grade": grade}
        fv = np.array([self._eco_feat(p)], dtype=float)
        proba = self.eco_model.predict_proba(fv)[0]
        predicted = round(float(self._eco_class_score @ proba), 1)
        if self.eco_explainer is None:
            return {"available": False, "grade": grade, "predicted": predicted}
        sv = np.array(self.eco_explainer.shap_values(fv))[0]   # (feat, cls)
        contrib = (sv * self._eco_class_score).sum(axis=1)     # (feat,)
        cat_contrib = float(contrib[:self._n_cat].sum())       # aggregate category effect
        feats = [{
            "feature": "Food category: " + p["category"],
            "value": "this category",
            "contribution": round(cat_contrib, 1),
        }, {
            "feature": "Organic label",
            "value": "yes" if p.get("organic") else "no",
            "contribution": round(float(contrib[self._n_cat]), 1),
        }, {
            "feature": "Processing (NOVA)",
            "value": ("group " + str(p["nova"])) if p.get("nova") else "n/a",
            "contribution": round(float(contrib[self._n_cat + 1]), 1),
        }, {
            "feature": "Additives",
            "value": str(p["additives_n"]) if p.get("additives_n") is not None else "n/a",
            "contribution": round(float(contrib[self._n_cat + 2]), 1),
        }]
        feats.sort(key=lambda d: abs(d["contribution"]), reverse=True)
        return {
            "available": True,
            "base": round(self._eco_shap_base, 1),
            "predicted": predicted,
            "grade": grade,
            "features": feats,
        }

    def shap_grades(self, p):
        """Per-grade SHAP waterfall data, exactly as in the project notebook
        (section 5): for every Nutri-Score grade A-E we expose how each nutrient
        pushes the model's probability of THAT grade up or down, starting from
        the base value E[f(x)] and ending at the predicted probability f(x).

        The web UI uses this to render a waterfall with a grade selector, the
        same interaction as the Streamlit prototype's 'Explain probability of
        grade' dropdown.
        """
        fv = np.array([[p["nutrients"][k] for k in ML_FEATURES]], dtype=float)
        proba = self.model.predict_proba(fv)[0]
        predicted_grade = self.classes_[int(np.argmax(proba))].upper()
        if self.explainer is None:
            return {"available": False, "predicted_grade": predicted_grade,
                    "features": ML_FEATURES, "grades": []}
        sv = np.array(self.explainer.shap_values(fv))[0]   # (feat, cls)
        ev = np.array(self.explainer.expected_value)        # (cls,)
        labels = [NUTRIENT_LABEL[k] for k in ML_FEATURES]
        values = [round(p["nutrients"][k], 1) for k in ML_FEATURES]
        units = ["kcal" if k == "energy_kcal" else "g" for k in ML_FEATURES]
        grades = []
        for ci, c in enumerate(self.classes_):
            contribs = [round(float(sv[fi, ci]), 4) for fi in range(len(ML_FEATURES))]
            grades.append({
                "grade": c.upper(),
                "base": round(float(ev[ci]), 4),       # E[P(grade)]
                "fx": round(float(proba[ci]), 4),      # P(grade) for this product
                "contribs": contribs,                  # signed, per feature
            })
        return {
            "available": True,
            "predicted_grade": predicted_grade,
            "features": labels,
            "values": values,
            "units": units,
            "grades": grades,
        }

    def detail(self, product_id):
        """Everything the product-detail page needs in one payload:
        the product, its three radar profiles, the SHAP explanation, and a
        tidy per-100 g nutrient table."""
        p = self.by_id.get(product_id)
        if p is None:
            return None
        n = p["nutrients"]
        nutrient_table = [
            {"label": "Energy", "value": n["energy_kcal"], "unit": "kcal"},
            {"label": "Sugars", "value": n["sugars"], "unit": "g"},
            {"label": "Fat", "value": n["fat"], "unit": "g"},
            {"label": "Saturated fat", "value": n["saturated_fat"], "unit": "g"},
            {"label": "Protein", "value": n["proteins"], "unit": "g"},
            {"label": "Fibre", "value": n["fiber"], "unit": "g"},
            {"label": "Salt", "value": n["salt"], "unit": "g"},
        ]
        return {
            **self.public(p),
            "radar": p["radar"],
            "nutrition_radar": self.nutrition_radar(p),
            "eco_radar": self.eco_radar(p),
            "shap": self.shap_attribution(p),
            "shap_grades": self.shap_grades(p),
            "eco_shap": self.eco_attribution(p),
            "nutrient_table": nutrient_table,
            "additives_n": p.get("additives_n"),
        }

    def _explain(self, alt, base, kind):
        """Plain-language, max two sentences (FR-06)."""
        em_a, em_b = alt["eco_metrics"], base["eco_metrics"]
        na, nb = alt["nutrients"], base["nutrients"]
        bits = []
        if kind == "Better for Earth":
            if em_b["co2_kg"] > 0:
                pct = round((em_b["co2_kg"] - em_a["co2_kg"]) / em_b["co2_kg"] * 100)
                if pct > 0:
                    bits.append(f"about {pct}% less estimated CO\u2082")
            if em_b["water_l"] > 0:
                wp = round((em_b["water_l"] - em_a["water_l"]) / em_b["water_l"] * 100)
                if wp > 0:
                    bits.append(f"{wp}% less estimated water")
            lead = "A greener pick"
        elif kind == "Better for You":
            if nb["sugars"] - na["sugars"] > 1:
                bits.append(f"{round(nb['sugars'] - na['sugars'], 1)} g less sugar")
            if na["proteins"] - nb["proteins"] > 0.5:
                bits.append(f"{round(na['proteins'] - nb['proteins'], 1)} g more protein")
            if nb["salt"] - na["salt"] > 0.1:
                bits.append(f"{round(nb['salt'] - na['salt'], 2)} g less salt")
            lead = "A healthier pick"
        else:
            lead = "Better on both health and environment"
        gains = ", ".join(bits[:2]) if bits else "a better overall balance"
        s1 = f"{lead}: {gains}."
        s2 = (f"Nutri-Score {alt['nutriscore'].upper()} and Eco-Score "
              f"{alt['ecoscore'].upper()} (yours: {base['nutriscore'].upper()}/"
              f"{base['ecoscore'].upper()}).")
        return f"{s1} {s2}"

    def _contrastive(self, alt, base):
        """Why this rather than your product -- the delta on both axes."""
        return {
            "health_delta": round(alt["health_score"] - base["health_score"], 1),
            "eco_delta": round(alt["eco_score"] - base["eco_score"], 1),
            "co2_delta": round(base["eco_metrics"]["co2_kg"] - alt["eco_metrics"]["co2_kg"], 2),
            "sugar_delta": round(base["nutrients"]["sugars"] - alt["nutrients"]["sugars"], 1),
            "protein_delta": round(alt["nutrients"]["proteins"] - base["nutrients"]["proteins"], 1),
        }

    # ------------------------------------------------------------ overview
    def overview(self):
        """Dataset-wide statistics for the overview/insights dashboard."""
        from collections import Counter
        ns = Counter(p["nutriscore"] for p in self.products)
        es = Counter(p["ecoscore"] for p in self.products)
        cats = Counter(p["category"] for p in self.products)
        # average sugar per nutri grade (shows the model learns something real)
        sugar_by_grade = {}
        for g in "abcde":
            vals = [p["nutrients"]["sugars"] for p in self.products if p["nutriscore"] == g]
            sugar_by_grade[g] = round(float(np.mean(vals)), 1) if vals else 0
        co2_by_eco = {}
        for g in "abcde":
            vals = [p["eco_metrics"]["co2_kg"] for p in self.products if p["ecoscore"] == g]
            co2_by_eco[g] = round(float(np.mean(vals)), 2) if vals else 0
        return {
            "total": len(self.products),
            "with_image": sum(1 for p in self.products if p["image"]),
            "categories_n": len(cats),
            "model_accuracy": round(self.train_accuracy * 100, 1),
            "nutriscore_dist": {g: ns.get(g, 0) for g in "abcde"},
            "ecoscore_dist": {g: es.get(g, 0) for g in "abcde"},
            "category_dist": dict(cats.most_common()),
            "sugar_by_grade": sugar_by_grade,
            "co2_by_eco": co2_by_eco,
            "feature_importance": {NUTRIENT_LABEL[k]: round(v, 3)
                                   for k, v in sorted(self.feature_importance.items(),
                                                      key=lambda x: -x[1])},
            "shap_importance": {NUTRIENT_LABEL[k]: round(v, 4)
                                for k, v in sorted(self.shap_importance.items(),
                                                   key=lambda x: -x[1])},
            "eco_feature_importance": dict(sorted(self.eco_feature_importance.items(),
                                                  key=lambda x: -x[1])),
            "eco_accuracy": getattr(self, "eco_accuracy", None),
            "ml_predicted": None,
            "allergens_available": sorted(set(a for p in self.products for a in p["allergens"])),
        }

    # ---------------------------------------------------------------- helpers
    def public(self, p):
        """The subset of a product safe to send to the browser."""
        return {
            "id": p["id"], "code": p["code"], "name": p["name"], "brand": p["brand"],
            "category": p["category"], "subcategory": p["subcategory"],
            "image": p["image"], "image_large": p.get("image_large", ""),
            "off_url": p["off_url"], "nutriscore": p["nutriscore"], "ecoscore": p["ecoscore"],
            "nova": p.get("nova"), "organic": p["organic"], "labels": p["labels"],
            "additives_n": p.get("additives_n"),
            "ingredients_text": p.get("ingredients_text", ""),
            "ingredients_n": p.get("ingredients_n"),
            "environmental_score": p.get("environmental_score"),
            "allergens": p["allergens"], "origins": p["origins"], "countries": p["countries"],
            "nutrients": p["nutrients"], "eco_metrics": p["eco_metrics"],
            "health_score": p["health_score"], "eco_score": p["eco_score"],
        }

    def get(self, product_id):
        p = self.by_id.get(product_id)
        return self.public(p) if p else None
