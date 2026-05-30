# =============================================================================
# BiteRec — Streamlit Web App
# Transparent Multi-Objective Food Recommendations
# =============================================================================

import logging
import os
import sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Ensure biterec package is importable when run from project root
sys.path.insert(0, os.path.dirname(__file__))

from biterec.config import (
    COMMON_ALLERGENS,
    DEFAULT_HEALTH_WEIGHT,
    NUTRISCORE_COLORS,
    ECOSCORE_COLORS,
)
from biterec.data_loader import load_data
from biterec.ml_model import NutriScoreModel
from biterec.scoring import score_dataframe, build_radar_df, co2_to_car_km, is_organic, origin_to_distance
from biterec.recommender import search_product, apply_allergen_filter, recommend, build_search_index, SearchIndex
from biterec.explainer import build_explanations, nutrient_attribution, contrastive_table

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="BiteRec — Smart Food Recommendations",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap');

  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
  }
  h1, h2, h3 {
    font-family: 'DM Serif Display', serif !important;
  }
  .stApp { background: #f7f6f2; }

  /* Card styles */
  .bite-card {
    background: white;
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    height: 100%;
    border-top: 4px solid #e0e0e0;
  }
  .bite-card.health { border-top-color: #38a169; }
  .bite-card.eco    { border-top-color: #2b6cb0; }
  .bite-card.winwin { border-top-color: #d4a017; }
  .bite-card.original { border-top-color: #718096; }

  .card-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
  }
  .badge-health  { background: #c6f6d5; color: #22543d; }
  .badge-eco     { background: #bee3f8; color: #2c5282; }
  .badge-winwin  { background: #fefcbf; color: #744210; }
  .badge-original { background: #e2e8f0; color: #2d3748; }

  .grade-pill {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 8px;
    color: white;
    font-weight: 700;
    font-size: 0.9rem;
    margin: 2px;
  }

  .explanation-box {
    background: #f0fff4;
    border-left: 3px solid #38a169;
    padding: 0.8rem 1rem;
    border-radius: 0 8px 8px 0;
    font-size: 0.88rem;
    margin-top: 0.8rem;
    color: #2d3748;
  }
  .explanation-box.eco {
    background: #ebf8ff;
    border-left-color: #2b6cb0;
  }
  .explanation-box.winwin {
    background: #fffff0;
    border-left-color: #d4a017;
  }

  .eco-metric {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: #e6fffa;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 0.8rem;
    color: #234e52;
    font-weight: 500;
  }

  .source-link {
    font-size: 0.75rem;
    color: #718096;
    margin-top: 0.4rem;
  }

  .metric-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 0.6rem 0; }
  .nutrient-chip {
    background: #edf2f7;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.78rem;
    color: #4a5568;
  }

  div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
def _init_state():
    defaults = {
        "df": None,
        "model": None,
        "data_loaded": False,
        "search_results": None,
        "selected_product": None,
        "recommendation": None,
        "explanations": None,
        "allergens": [],
        "health_weight": DEFAULT_HEALTH_WEIGHT,
        "search_query": "",
        "show_details": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading Open Food Facts dataset — this may take a minute for large files…")
def get_data_and_model():
    df = load_data()
    model = NutriScoreModel()
    model.fit_or_load(df)
    df = model.fill_missing(df)
    df = score_dataframe(df, DEFAULT_HEALTH_WEIGHT)
    search_idx = build_search_index(df)
    return df, model, search_idx


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar():
    with st.sidebar:
        st.markdown("## ⚙️ Your Preferences")

        # --- Priority slider (FR-03)
        st.markdown("### 🎚️ Health ↔ Planet Balance")
        st.caption("Default is 70/30 based on user research (6 of 8 participants prioritised health).")
        health_pct = st.slider(
            "Health weight",
            min_value=0, max_value=100,
            value=int(st.session_state.health_weight * 100),
            step=5,
            format="%d%%",
            label_visibility="collapsed",
        )
        col1, col2 = st.columns(2)
        col1.markdown(f"🫀 **{health_pct}% Health**")
        col2.markdown(f"🌱 **{100 - health_pct}% Planet**")

        new_weight = health_pct / 100
        if new_weight != st.session_state.health_weight:
            st.session_state.health_weight = new_weight
            # Trigger re-recommendation if a product is selected
            if st.session_state.selected_product is not None:
                st.session_state.recommendation = None

        st.divider()

        # --- Allergen filter (FR-04)
        st.markdown("### 🚫 Allergen Filter")
        st.caption("Products containing these will **never** appear in recommendations.")

        common = list(COMMON_ALLERGENS.keys())
        selected_allergens = st.multiselect(
            "Common allergens",
            options=common,
            default=st.session_state.allergens,
            label_visibility="collapsed",
        )
        custom = st.text_input(
            "Or type a custom allergen",
            placeholder="e.g. mustard, lupin…",
        )
        if custom.strip():
            for a in custom.split(","):
                a = a.strip().lower()
                if a and a not in selected_allergens:
                    selected_allergens.append(a)

        st.session_state.allergens = selected_allergens
        if selected_allergens:
            st.success(f"Active: {', '.join(selected_allergens)}")

        st.divider()

        # --- Advanced nutrient filters (FR-02)
        st.markdown("### 🔬 Advanced Filters")
        with st.expander("Nutritional criteria"):
            min_protein = st.slider("Min protein (g/100g)", 0, 40, 0)
            max_sugar = st.slider("Max sugar (g/100g)", 0, 100, 100)
            max_salt = st.slider("Max salt (g/100g)", 0, 10, 10)
            only_organic = st.checkbox("Organic only 🌿")

        st.session_state["adv_filters"] = {
            "min_protein": min_protein,
            "max_sugar": max_sugar,
            "max_salt": max_salt,
            "only_organic": only_organic,
        }

        st.divider()
        st.markdown(
            "📖 Data: [Open Food Facts](https://world.openfoodfacts.org) (ODbL licence)",
            unsafe_allow_html=False,
        )


# ---------------------------------------------------------------------------
# Grade pill HTML helper
# ---------------------------------------------------------------------------
def grade_pill(grade: str, score_type: str = "nutri") -> str:
    g = str(grade).lower()
    colors = NUTRISCORE_COLORS if score_type == "nutri" else ECOSCORE_COLORS
    color = colors.get(g, colors["unknown"])
    label = g.upper() if g in "abcde" else "?"
    return f'<span class="grade-pill" style="background:{color};">{label}</span>'


# ---------------------------------------------------------------------------
# Product card renderer
# ---------------------------------------------------------------------------
def render_product_card(row: pd.Series, card_type: str, explanation: str | None = None):
    type_map = {
        "original": ("original", "badge-original", "🔍 Original"),
        "health":   ("health",   "badge-health",   "💚 Better for You"),
        "eco":      ("eco",      "badge-eco",       "🌍 Better for Earth"),
        "winwin":   ("winwin",   "badge-winwin",    "🌟 Win-Win Pick"),
    }
    card_class, badge_class, badge_label = type_map.get(card_type, type_map["original"])

    name = str(row.get("product_name", "Unknown product")).title()
    brand = str(row.get("brands", "")).title() or "—"
    image_url = str(row.get("image_url", ""))

    ns_grade = str(row.get("nutriscore_grade", "?"))
    es_grade = str(row.get("ecoscore_grade", "?"))
    co2 = row.get("co2_g_per_100g", None)
    co2_str = co2_to_car_km(float(co2)) if co2 and not pd.isna(co2) else None

    protein = row.get("proteins_100g")
    sugar = row.get("sugars_100g")
    salt = row.get("salt_100g")

    off_code = str(row.get("code", "")).strip()
    off_url = f"https://world.openfoodfacts.org/product/{off_code}" if off_code and off_code != "nan" else None

    with st.container():
        st.markdown(f'<div class="bite-card {card_class}">', unsafe_allow_html=True)

        # Badge + product image
        col_img, col_info = st.columns([1, 3])
        with col_img:
            if image_url and image_url not in ("nan", ""):
                try:
                    st.image(image_url, use_container_width=True)
                except Exception:
                    st.markdown("🖼️", unsafe_allow_html=True)
            else:
                st.markdown('<div style="font-size:3rem;text-align:center">🛒</div>', unsafe_allow_html=True)

        with col_info:
            st.markdown(
                f'<span class="card-badge {badge_class}">{badge_label}</span>',
                unsafe_allow_html=True,
            )
            st.markdown(f"**{name}**")
            st.caption(f"Brand: {brand}")

            # Scores with icons + text (NFR-02 accessibility)
            score_html = (
                f"Nutri-Score {grade_pill(ns_grade, 'nutri')} &nbsp; "
                f"Eco-Score {grade_pill(es_grade, 'eco')}"
            )
            st.markdown(score_html, unsafe_allow_html=True)

        # Nutrient chips
        chips = []
        if protein and not pd.isna(protein):
            chips.append(f"🥩 Protein: {protein:.1f}g")
        if sugar and not pd.isna(sugar):
            chips.append(f"🍬 Sugar: {sugar:.1f}g")
        if salt and not pd.isna(salt):
            chips.append(f"🧂 Salt: {salt:.1f}g")
        if chips:
            st.markdown(
                " &nbsp; ".join(f'<span class="nutrient-chip">{c}</span>' for c in chips),
                unsafe_allow_html=True,
            )

        # Concrete eco metrics (FR-08)
        eco_parts = []
        if co2_str:
            eco_parts.append(f"🚗 {co2_str}")
        if is_organic(row):
            eco_parts.append("🌿 Organic")
        origin = origin_to_distance(row)
        if origin:
            eco_parts.append(f"📍 {origin}")
        if eco_parts:
            st.markdown(
                " &nbsp; ".join(f'<span class="eco-metric">{p}</span>' for p in eco_parts),
                unsafe_allow_html=True,
            )

        # XAI explanation (FR-06)
        if explanation:
            box_class = "eco" if card_type == "eco" else ("winwin" if card_type == "winwin" else "")
            st.markdown(
                f'<div class="explanation-box {box_class}">💡 {explanation}</div>',
                unsafe_allow_html=True,
            )

        # Source transparency (FR-09)
        if off_url:
            st.markdown(
                f'<div class="source-link">📎 Source: <a href="{off_url}" target="_blank">Open Food Facts</a></div>',
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Radar chart (FR-07)
# ---------------------------------------------------------------------------
def render_radar_chart(products_data: list[tuple[str, pd.Series]]):
    radar_df = build_radar_df(products_data)
    dimensions = radar_df["Dimension"].unique().tolist()
    colors = ["#718096", "#38a169", "#2b6cb0"]

    fig = go.Figure()
    for i, (label, _) in enumerate(products_data):
        subset = radar_df[radar_df["Product"] == label]
        vals = subset.set_index("Dimension")["Score"].reindex(dimensions).tolist()
        vals_closed = vals + [vals[0]]
        dims_closed = dimensions + [dimensions[0]]
        fig.add_trace(go.Scatterpolar(
            r=vals_closed,
            theta=dims_closed,
            fill="toself",
            fillcolor=colors[i % len(colors)],
            opacity=0.2,
            line=dict(color=colors[i % len(colors)], width=2),
            name=label,
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1], tickvals=[0.25, 0.5, 0.75, 1.0]),
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        margin=dict(l=40, r=40, t=40, b=60),
        height=400,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Apply advanced filters helper
# ---------------------------------------------------------------------------
def apply_adv_filters(df: pd.DataFrame) -> pd.DataFrame:
    f = st.session_state.get("adv_filters", {})
    if f.get("min_protein", 0) > 0:
        df = df[df["proteins_100g"].fillna(0) >= f["min_protein"]]
    if f.get("max_sugar", 100) < 100:
        df = df[df["sugars_100g"].fillna(999) <= f["max_sugar"]]
    if f.get("max_salt", 10) < 10:
        df = df[df["salt_100g"].fillna(999) <= f["max_salt"]]
    if f.get("only_organic"):
        df = df[df.apply(is_organic, axis=1)]
    return df


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
def main():
    render_sidebar()

    # --- Header
    st.markdown(
        "<h1 style='margin-bottom:0'>🥗 BiteRec</h1>"
        "<p style='color:#718096;font-size:1.05rem;margin-top:0'>"
        "Transparent food recommendations — better for you <em>and</em> the planet.</p>",
        unsafe_allow_html=True,
    )

    # --- Load data
    if not st.session_state.data_loaded:
        try:
            df, model, search_idx = get_data_and_model()
            st.session_state.df = df
            st.session_state.model = model
            st.session_state.search_idx = search_idx
            st.session_state.data_loaded = True
        except FileNotFoundError as e:
            st.error(str(e))
            st.info(
                "📥 **Download the dataset:**  "
                "Go to [Open Food Facts data](https://world.openfoodfacts.org/data), "
                "download the CSV export, and place it in the `data/` folder."
            )
            st.stop()

    df: pd.DataFrame = st.session_state.df

    # --- Stats strip
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 Products", f"{len(df):,}")
    known_ns = (df["nutriscore_grade"].isin(list("abcde"))).sum()
    col2.metric("🏷️ Nutri-Score coverage", f"{known_ns/len(df)*100:.0f}%")
    known_es = (df["ecoscore_grade"].isin(list("abcde"))).sum()
    col3.metric("🌱 Eco-Score coverage", f"{known_es/len(df)*100:.0f}%")
    predicted = df.get("nutriscore_predicted", pd.Series(False, index=df.index)).sum()
    col4.metric("🤖 ML-predicted grades", f"{predicted:,}")

    st.divider()

    # --- Tabs
    tab_rec, tab_ai = st.tabs(["📊 Recommendations", "🤖 AI Details"])

    # =========================================================================
    # TAB 1 — Recommendations
    # =========================================================================
    with tab_rec:
        # Search bar (FR-01)
        query = st.text_input(
            "🔍 Search for a food product",
            placeholder="e.g. whole milk, greek yoghurt, oat biscuits…",
            value=st.session_state.search_query,
        )

        if query != st.session_state.search_query:
            st.session_state.search_query = query
            st.session_state.selected_product = None
            st.session_state.recommendation = None
            st.session_state.search_results = None

        if query.strip():
            # Search — only re-filter if query or filters have changed
            filter_key = (query, tuple(st.session_state.allergens),
                          str(st.session_state.get("adv_filters", {})))
            if (st.session_state.search_results is None
                    or query != st.session_state.get("_last_query")
                    or filter_key != st.session_state.get("_last_filter_key")):
                search_idx = st.session_state.get("search_idx")
                raw_results = search_product(search_idx if search_idx else df, query)
                filtered_df = apply_adv_filters(raw_results)
                results = apply_allergen_filter(filtered_df, st.session_state.allergens)
                st.session_state.search_results = results
                st.session_state["_last_query"] = query
                st.session_state["_last_filter_key"] = filter_key

            results: pd.DataFrame = st.session_state.search_results

            if len(results) == 0:
                st.warning(
                    f"No products found for **{query}**. "
                    "Try a different search term or adjust your filters."
                )
            else:
                # Product selector
                product_names = results["product_name"].tolist()
                display_names = [
                    f"{n.title()} — {str(b).title()}" if b else n.title()
                    for n, b in zip(results["product_name"], results["brands"])
                ]
                chosen_idx = st.selectbox(
                    f"Found {len(results)} products — select one:",
                    options=range(len(display_names)),
                    format_func=lambda i: display_names[i],
                )
                selected_row = results.iloc[chosen_idx]

                # Run recommendation
                if (
                    st.session_state.recommendation is None
                    or st.session_state.selected_product is None
                    or st.session_state.selected_product.get("product_name") != selected_row.get("product_name")
                ):
                    with st.spinner("Finding best alternatives…"):
                        rec = recommend(
                            df,
                            selected_row,
                            st.session_state.allergens,
                            st.session_state.health_weight,
                        )
                        expl = build_explanations(rec)
                        st.session_state.recommendation = rec
                        st.session_state.explanations = expl
                        st.session_state.selected_product = selected_row

                rec = st.session_state.recommendation
                expl = st.session_state.explanations

                # --- Three cards (FR-05, NFR-03)
                st.markdown("### Your Results")
                cols = st.columns(3)

                with cols[0]:
                    render_product_card(rec.searched, "original")

                with cols[1]:
                    if rec.better_for_you is not None:
                        card_type = "winwin" if rec.win_win else "health"
                        render_product_card(
                            rec.better_for_you,
                            card_type,
                            explanation=expl.get("better_for_you_text"),
                        )
                    else:
                        st.info("No health alternative found in this category.")

                with cols[2]:
                    if rec.win_win:
                        st.markdown(
                            '<div style="background:#fffff0;border-radius:12px;padding:1.2rem;'
                            'text-align:center;border:2px dashed #d4a017">'
                            '<p style="font-size:1.1rem">🌟 <strong>Win-Win!</strong></p>'
                            '<p style="font-size:0.9rem;color:#744210">'
                            'The same alternative is both healthier <em>and</em> more sustainable.</p>'
                            '</div>',
                            unsafe_allow_html=True,
                        )
                    elif rec.better_for_earth is not None:
                        render_product_card(
                            rec.better_for_earth,
                            "eco",
                            explanation=expl.get("better_for_earth_text"),
                        )
                    else:
                        st.info("No eco alternative found in this category.")

                st.divider()

                # --- Radar chart (FR-07)
                st.markdown("### 🕸️ Side-by-Side Comparison")
                chart_products = [("Original", rec.searched)]
                if rec.better_for_you is not None:
                    chart_products.append(("Better for You", rec.better_for_you))
                if rec.better_for_earth is not None and not rec.win_win:
                    chart_products.append(("Better for Earth", rec.better_for_earth))
                render_radar_chart(chart_products)

                # Source transparency note (FR-09)
                st.caption(
                    "📎 All data from [Open Food Facts](https://world.openfoodfacts.org) "
                    "(Open Database Licence). CO₂ figures are estimates derived from Eco-Score grade "
                    "and are labelled as such in the UI."
                )

                # --- XAI detail expander (UC-04)
                with st.expander("🔍 Why is this recommended? (Full explanation)"):
                    if rec.better_for_you is not None:
                        st.markdown("#### 💚 Better for You")
                        st.info(expl.get("better_for_you_text", "—"))
                        diffs = expl.get("better_for_you_diffs", [])
                        if diffs:
                            for d in diffs:
                                arrow = "⬆️" if d["delta_pct"] > 0 else "⬇️"
                                icon = "✅" if d["improved"] else "⚠️"
                                st.markdown(
                                    f"{icon} **{d['label'].title()}**: "
                                    f"{arrow} {abs(d['delta_pct']):.0f}% vs original"
                                )

                    if rec.better_for_earth is not None and not rec.win_win:
                        st.markdown("#### 🌍 Better for Earth")
                        st.info(expl.get("better_for_earth_text", "—"))

    # =========================================================================
    # TAB 2 — AI Details
    # =========================================================================
    with tab_ai:
        st.markdown("### 🤖 Model Insight")
        st.caption(
            "The Random Forest model is trained on products with known Nutri-Score grades "
            "and predicts missing grades for the rest. "
            "SHAP (SHapley Additive exPlanations) shows exactly which nutrients drove each prediction."
        )

        model: NutriScoreModel = st.session_state.model

        # ── Global feature importance (RF built-in + SHAP mean|φ|) ──────────
        col_fi, col_shap = st.columns(2)

        with col_fi:
            st.markdown("#### 📊 RF Feature Importance")
            importances = model.feature_importances()
            if not importances.empty:
                imp_df = importances.reset_index()
                imp_df.columns = ["Feature", "Importance"]
                imp_df["Feature"] = (
                    imp_df["Feature"]
                    .str.replace("_100g", " /100g")
                    .str.replace("-", " ")
                )
                fig_fi = go.Figure(go.Bar(
                    x=imp_df["Importance"],
                    y=imp_df["Feature"],
                    orientation="h",
                    marker_color="#38a169",
                    text=imp_df["Importance"].map(lambda x: f"{x:.3f}"),
                    textposition="outside",
                ))
                fig_fi.update_layout(
                    height=300, margin=dict(l=10, r=60, t=10, b=10),
                    xaxis_title="Importance", paper_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(autorange="reversed"), font=dict(family="DM Sans"),
                )
                st.plotly_chart(fig_fi, use_container_width=True)
            else:
                st.info("Train the model first by searching for a product.")

        with col_shap:
            st.markdown("#### 🔮 SHAP Global Importance (mean |φ|)")
            if model.shap_explainer is not None:
                with st.spinner("Computing SHAP values…"):
                    shap_summary = model.shap_summary_data(df, n=300)
                if shap_summary:
                    from biterec.explainer import shap_global_importance_df
                    shap_gi = shap_global_importance_df(shap_summary)
                    if not shap_gi.empty:
                        fig_shap = go.Figure(go.Bar(
                            x=shap_gi["importance"],
                            y=shap_gi["feature_label"],
                            orientation="h",
                            marker_color="#805ad5",
                            text=shap_gi["importance"].map(lambda x: f"{x:.3f}"),
                            textposition="outside",
                        ))
                        fig_shap.update_layout(
                            height=300, margin=dict(l=10, r=60, t=10, b=10),
                            xaxis_title="Mean |SHAP value|",
                            paper_bgcolor="rgba(0,0,0,0)",
                            yaxis=dict(autorange="reversed"),
                            font=dict(family="DM Sans"),
                        )
                        st.plotly_chart(fig_shap, use_container_width=True)
            else:
                st.info("SHAP explainer not available. Search for a product first.")

        # ── Per-product SHAP waterfall (notebook § 5 local explanation) ─────
        rec = st.session_state.recommendation
        if rec is not None:
            st.divider()
            st.markdown("#### 🌊 SHAP Waterfall — Why did this product get its Nutri-Score?")
            st.caption(
                "The waterfall shows how each nutrient pushed the model's prediction "
                "away from the average (base value) towards the final grade probability. "
                "Red bars increase the probability; blue bars decrease it. "
                "Following the methodology in off_nutriscore_01.ipynb § 5."
            )

            from biterec.explainer import shap_waterfall_df

            grade_options = ["A", "B", "C", "D", "E"]
            target_grade = st.selectbox(
                "Explain probability of grade:",
                options=grade_options,
                index=0,
                help="Select which Nutri-Score grade to explain. 'A' = healthiest.",
            )

            if model.shap_explainer is not None:
                with st.spinner("Computing SHAP values for this product…"):
                    shap_data = model.shap_local(rec.searched)

                if shap_data:
                    wf_df = shap_waterfall_df(shap_data, target_class=target_grade)

                    if not wf_df.empty:
                        # Base value line
                        classes_upper = [str(c).upper() for c in shap_data["classes"]]
                        base_vals = shap_data["base"]
                        idx = classes_upper.index(target_grade) if target_grade in classes_upper else 0
                        base_val = float(base_vals[idx]) if hasattr(base_vals, "__len__") else float(base_vals)
                        final_val = base_val + wf_df["shap_value"].sum()

                        colors = [
                            "#38a169" if v >= 0 else "#e53e3e"
                            for v in wf_df["shap_value"]
                        ]
                        labels = [
                            f"{'+' if v >= 0 else ''}{v:.3f} (val={row['value_label']})"
                            for v, (_, row) in zip(wf_df["shap_value"], wf_df.iterrows())
                        ]

                        fig_wf = go.Figure(go.Waterfall(
                            name="SHAP",
                            orientation="h",
                            measure=["relative"] * len(wf_df) + ["total"],
                            y=wf_df["feature_label"].tolist() + [f"f(x) = {final_val:.3f}"],
                            x=wf_df["shap_value"].tolist() + [0],
                            base=base_val,
                            text=labels + [f"Final: {final_val:.3f}"],
                            textposition="outside",
                            connector={"line": {"color": "#cbd5e0"}},
                            increasing={"marker": {"color": "#38a169"}},
                            decreasing={"marker": {"color": "#e53e3e"}},
                            totals={"marker": {"color": "#2b6cb0"}},
                        ))
                        fig_wf.add_vline(
                            x=base_val, line_dash="dash", line_color="#718096",
                            annotation_text=f"Base: {base_val:.3f}",
                            annotation_position="top right",
                        )
                        fig_wf.update_layout(
                            height=380,
                            margin=dict(l=10, r=120, t=20, b=20),
                            xaxis_title=f"SHAP value (impact on P(grade={target_grade}))",
                            paper_bgcolor="rgba(0,0,0,0)",
                            font=dict(family="DM Sans"),
                        )
                        st.plotly_chart(fig_wf, use_container_width=True)

                        # Legend / reading guide
                        st.markdown(
                            "**How to read this:** Each bar shows how much a nutrient "
                            f"*increased* (🟢) or *decreased* (🔴) the probability of grade **{target_grade}**. "
                            "The final bar (blue) is the model's total predicted probability."
                        )
            else:
                # Fallback: simple median-based attribution table
                st.info("SHAP not available — showing simple median-based attribution instead.")
                median_row = df[
                    ["energy-kcal_100g", "fat_100g", "saturated-fat_100g",
                     "sugars_100g", "fiber_100g", "proteins_100g", "salt_100g"]
                ].median()
                attr_df = nutrient_attribution(rec.searched, median_row)
                if not attr_df.empty:
                    st.dataframe(attr_df, use_container_width=True, hide_index=True)

            # ── Contrastive comparison tables ────────────────────────────────
            if rec.better_for_you is not None:
                st.divider()
                st.markdown("#### 📋 Contrastive Comparison — Original vs Better for You")
                ct = contrastive_table(rec.searched, rec.better_for_you, "Better for You")
                st.dataframe(ct, use_container_width=True, hide_index=True)

            if rec.better_for_earth is not None and not rec.win_win:
                st.divider()
                st.markdown("#### 📋 Contrastive Comparison — Original vs Better for Earth")
                ct2 = contrastive_table(rec.searched, rec.better_for_earth, "Better for Earth")
                st.dataframe(ct2, use_container_width=True, hide_index=True)

        else:
            st.info("Search for a product in the **Recommendations** tab to unlock per-product AI details.")


if __name__ == "__main__":
    main()
