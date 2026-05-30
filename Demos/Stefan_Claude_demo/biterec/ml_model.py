"""
BiteRec — machine-learning layer.

A RandomForest classifier predicts the Nutri-Score grade (A–E) from a product's
nutrient profile, following the approach in the team's `off_nutriscore_01.ipynb`
notebook. The model serves two purposes:

  1. Coverage: ~80 % of products in the export have an "unknown" Nutri-Score.
     The model fills these gaps from the nutrient values so far more products
     become recommendable.
  2. Explainability (XAI / FR-06): the trained model exposes feature
     importances, and we compute a per-product nutrient contribution that drives
     the plain-language explanations.

The model is trained once and cached to disk (models/nutriscore_rf.joblib).
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

from . import config as C


def _training_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Rows with a real grade (A–E) and a complete nutrient profile."""
    mask = df[C.COL_NUTRISCORE_GRADE].isin(C.VALID_NUTRI_GRADES) & df["has_full_nutrients"]
    return df.loc[mask, C.NUTRIENT_FEATURES + [C.COL_NUTRISCORE_GRADE]]


class NutriScoreModel:
    """Thin wrapper around a RandomForestClassifier."""

    def __init__(self, clf: RandomForestClassifier, accuracy: float,
                 n_train: int, medians: dict):
        self.clf = clf
        self.accuracy = accuracy
        self.n_train = n_train
        # Dataset medians per feature, used as a baseline for local XAI.
        self.medians = medians

    # ---- training -------------------------------------------------------- #
    @classmethod
    def train(cls, df: pd.DataFrame) -> "NutriScoreModel":
        frame = _training_frame(df)
        X = frame[C.NUTRIENT_FEATURES]
        y = frame[C.COL_NUTRISCORE_GRADE]

        if len(frame) < 30 or y.nunique() < 2:
            raise ValueError(
                "Not enough labelled rows to train the Nutri-Score model."
            )

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        clf = RandomForestClassifier(
            n_estimators=200, random_state=42, class_weight="balanced", n_jobs=-1
        )
        clf.fit(X_train, y_train)
        acc = accuracy_score(y_test, clf.predict(X_test))
        medians = X.median().to_dict()
        return cls(clf, float(acc), len(frame), medians)

    # ---- persistence ----------------------------------------------------- #
    def save(self, path=C.MODEL_PATH) -> None:
        joblib.dump(
            {"clf": self.clf, "accuracy": self.accuracy,
             "n_train": self.n_train, "medians": self.medians},
            path,
        )

    @classmethod
    def load(cls, path=C.MODEL_PATH) -> "NutriScoreModel":
        blob = joblib.load(path)
        return cls(blob["clf"], blob["accuracy"], blob["n_train"], blob["medians"])

    # ---- inference ------------------------------------------------------- #
    def predict_grade(self, features: pd.DataFrame) -> np.ndarray:
        return self.clf.predict(features[C.NUTRIENT_FEATURES])

    @property
    def feature_importance(self) -> dict:
        return dict(zip(C.NUTRIENT_FEATURES, self.clf.feature_importances_))


def get_model(df: pd.DataFrame, force_retrain: bool = False) -> NutriScoreModel:
    """Load the cached model, training (and caching) it if needed."""
    if C.MODEL_PATH.exists() and not force_retrain:
        try:
            return NutriScoreModel.load()
        except Exception:
            pass
    model = NutriScoreModel.train(df)
    model.save()
    return model


def fill_predicted_grades(df: pd.DataFrame, model: NutriScoreModel) -> pd.DataFrame:
    """Add `effective_grade` (real grade where known, else ML prediction).

    Adds two columns:
      - effective_grade: the grade used for scoring (A–E or "" if impossible)
      - grade_is_predicted: True when the value came from the ML model
    """
    df = df.copy()
    df["effective_grade"] = df[C.COL_NUTRISCORE_GRADE]
    df["grade_is_predicted"] = False

    needs = (~df[C.COL_NUTRISCORE_GRADE].isin(C.VALID_NUTRI_GRADES)) & df["has_full_nutrients"]
    if needs.any():
        preds = model.predict_grade(df.loc[needs])
        df.loc[needs, "effective_grade"] = preds
        df.loc[needs, "grade_is_predicted"] = True

    # Anything still without a valid grade stays blank.
    df.loc[~df["effective_grade"].isin(C.VALID_NUTRI_GRADES), "effective_grade"] = ""
    return df
