"""BiteRec — transparent multi-objective food recommendation engine."""
from . import config, data_loader, ml_model, scoring, recommender, explainer

__all__ = ["config", "data_loader", "ml_model", "scoring", "recommender",
           "explainer", "build_catalog"]
__version__ = "1.0.0"


def build_catalog(force_retrain: bool = False):
    """End-to-end pipeline: load -> clean -> train/predict -> score.

    Returns (catalog_dataframe, model).
    """
    df = data_loader.load()
    model = ml_model.get_model(df, force_retrain=force_retrain)
    df = ml_model.fill_predicted_grades(df, model)
    df = scoring.add_scores(df)
    return df, model
