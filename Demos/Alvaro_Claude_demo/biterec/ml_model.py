# =============================================================================
# BiteRec — ML Model
# Random Forest classifier that predicts Nutri-Score grade (A–E).
# Uses SHAP (TreeExplainer) for XAI, following off_nutriscore_01.ipynb.
# =============================================================================

import os
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import shap

logger = logging.getLogger(__name__)

MODEL_PATH  = "models/nutriscore_rf.joblib"
SHAP_PATH   = "models/shap_explainer.joblib"

FEATURE_COLS = [
    "energy-kcal_100g",
    "sugars_100g",
    "fat_100g",
    "saturated-fat_100g",
    "proteins_100g",
    "salt_100g",
    "fiber_100g",
]

GRADE_ORDER = ["a", "b", "c", "d", "e"]


# ---------------------------------------------------------------------------
# Model class
# ---------------------------------------------------------------------------

class NutriScoreModel:
    """
    Thin wrapper around RandomForestClassifier + SHAP TreeExplainer.

    Usage
    -----
    model = NutriScoreModel()
    model.fit_or_load(df)
    df    = model.fill_missing(df)
    fi    = model.feature_importances()          # global importance Series
    shap_df = model.shap_local(row, X_background) # per-product attribution
    """

    def __init__(self):
        self.clf: RandomForestClassifier | None = None
        self.shap_explainer = None
        self.classes_: list[str] = []
        self.trained = False
        self._X_sample: pd.DataFrame | None = None  # small background for SHAP

    # ------------------------------------------------------------------
    def fit_or_load(self, df: pd.DataFrame) -> None:
        if os.path.exists(MODEL_PATH):
            try:
                self.clf = joblib.load(MODEL_PATH)
                self.classes_ = list(self.clf.classes_)
                self.trained = True
                logger.info("Nutri-Score model loaded from cache.")
                # Rebuild SHAP explainer (fast, no retraining needed)
                self._init_shap_explainer(df)
                return
            except Exception as e:
                logger.warning(f"Cache load failed ({e}); retraining.")

        self._train(df)

    # ------------------------------------------------------------------
    def _train(self, df: pd.DataFrame) -> None:
        """Train on rows with a known Nutri-Score grade (A–E)."""
        known = df[df["nutriscore_grade"].isin(GRADE_ORDER)].copy()
        logger.info(f"Training on {len(known):,} labelled products.")

        if len(known) < 50:
            logger.error("Too few labelled rows to train.")
            return

        X = _make_X(known)
        y = known["nutriscore_grade"].str.upper()  # match notebook

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        self.clf = RandomForestClassifier(
            n_estimators=100,    # matches notebook
            random_state=42,
            n_jobs=-1,
            class_weight="balanced",
        )
        self.clf.fit(X_train, y_train)
        self.classes_ = list(self.clf.classes_)
        self.trained = True

        acc = accuracy_score(y_test, self.clf.predict(X_test))
        logger.info(f"Accuracy: {acc:.2%}")
        logger.info("\n" + classification_report(y_test, self.clf.predict(X_test), zero_division=0))

        os.makedirs("models", exist_ok=True)
        joblib.dump(self.clf, MODEL_PATH)
        logger.info(f"Model saved → {MODEL_PATH}")

        self._init_shap_explainer(df)

    # ------------------------------------------------------------------
    def _init_shap_explainer(self, df: pd.DataFrame) -> None:
        """Initialise SHAP TreeExplainer with a small background sample."""
        if self.clf is None:
            return
        known = df[df["nutriscore_grade"].isin(GRADE_ORDER)]
        # 500-row background is enough for TreeExplainer
        sample = known.sample(min(500, len(known)), random_state=42)
        self._X_sample = _make_X(sample)
        try:
            self.shap_explainer = shap.TreeExplainer(self.clf)
            logger.info("SHAP TreeExplainer initialised.")
        except Exception as e:
            logger.warning(f"SHAP init failed: {e}")

    # ------------------------------------------------------------------
    def fill_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict Nutri-Score for rows where grade == 'unknown'."""
        if not self.trained or self.clf is None:
            return df

        mask = df["nutriscore_grade"] == "unknown"
        if mask.sum() == 0:
            return df

        subset = df[mask].copy()
        X = _make_X(subset)

        # Only predict rows with at least 3 non-zero features
        has_data = (X > 0).sum(axis=1) >= 3
        idx_valid = subset.index[has_data]

        if len(idx_valid) == 0:
            return df

        X_valid = _make_X(df.loc[idx_valid])
        preds = self.clf.predict(X_valid)
        # Store lowercase internally (consistent with the rest of the system)
        preds_lower = [p.lower() for p in preds]

        df = df.copy()
        df.loc[idx_valid, "nutriscore_grade"] = preds_lower
        df.loc[idx_valid, "nutriscore_predicted"] = True
        logger.info(f"Predicted Nutri-Score for {len(idx_valid):,} products.")
        return df

    # ------------------------------------------------------------------
    def feature_importances(self) -> pd.Series:
        """Global feature importances as a named Series (sorted desc)."""
        if not self.trained or self.clf is None:
            return pd.Series(dtype=float)
        return pd.Series(
            self.clf.feature_importances_,
            index=FEATURE_COLS,
        ).sort_values(ascending=False)

    # ------------------------------------------------------------------
    def shap_local(self, row: pd.Series) -> dict:
        """
        Compute SHAP values for a single product row.

        Returns a dict with:
          - 'values':   np.ndarray of shape (n_classes, n_features)
          - 'base':     np.ndarray of shape (n_classes,)
          - 'features': list of feature names
          - 'data':     list of feature values for this product
          - 'classes':  list of class labels ['A','B','C','D','E']

        Following off_nutriscore_01.ipynb § 5 (TreeExplainer).
        """
        if self.shap_explainer is None or self.clf is None:
            return {}
        try:
            X_row = _make_X(pd.DataFrame([row]))
            sv = self.shap_explainer.shap_values(X_row)
            # sklearn RF multiclass: sv shape = (n_samples, n_features, n_classes)
            sv_arr = np.array(sv)
            if sv_arr.ndim == 3:
                # (1, n_features, n_classes) → (n_features, n_classes)
                sv_arr = sv_arr[0]
            elif sv_arr.ndim == 2:
                # (1, n_features) single-class → (n_features, 1)
                sv_arr = sv_arr[0].reshape(-1, 1)
            base = self.shap_explainer.expected_value
            return {
                "values": sv_arr,           # (n_features, n_classes)
                "base": base,               # (n_classes,) array
                "features": FEATURE_COLS,
                "data": X_row.iloc[0].tolist(),
                "classes": self.classes_,
            }
        except Exception as e:
            logger.warning(f"SHAP local failed: {e}")
            return {}

    # ------------------------------------------------------------------
    def shap_summary_data(self, df: pd.DataFrame, n: int = 300) -> dict:
        """
        Compute SHAP values for a sample of the dataset (for global summary).
        Returns the same structure as shap_local but for n rows.
        """
        if self.shap_explainer is None:
            return {}
        try:
            known = df[df["nutriscore_grade"].isin(GRADE_ORDER)]
            sample = known.sample(min(n, len(known)), random_state=1)
            X = _make_X(sample)
            sv = self.shap_explainer.shap_values(X)
            sv_arr = np.array(sv)
            # (n_samples, n_features, n_classes) or (n_samples, n_features)
            return {
                "values": sv_arr,            # (n_samples, n_features, n_classes)
                "base": self.shap_explainer.expected_value,
                "features": FEATURE_COLS,
                "X": X,
                "classes": self.classes_,
            }
        except Exception as e:
            logger.warning(f"SHAP summary failed: {e}")
            return {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_X(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract and impute the feature matrix.
    Missing columns filled as 0 (as per notebook § 2 imputation logic).
    """
    X = pd.DataFrame(index=df.index)
    for col in FEATURE_COLS:
        if col in df.columns:
            X[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            X[col] = 0.0
    return X.astype(np.float32)
