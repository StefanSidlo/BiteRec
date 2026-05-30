"""
BiteRec — Streamlit web application (frontend).

Run with:  streamlit run app.py   (or: python run.py)

Implements every functional requirement from requirements_and_use_cases.md:
search (FR-01), multi-criteria filters (FR-02), priority slider (FR-03),
allergen hard constraints (FR-04), two-alternative recommendation (FR-05),
XAI explanations (FR-06), radar chart (FR-07), concrete eco metrics (FR-08),
data-source transparency (FR-09) and a no-login core flow (FR-10).
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import biterec
from biterec import config as C
from biterec import recommender, explainer, scoring

st.set_page_config(page_title="BiteRec", page_icon="🥗", layout="wide")

# --------------------------------------------------------------------------- #
# Styling — every colour is paired with an icon/label for accessibility (NFR-02)
# --------------------------------------------------------------------------- #
st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1250px;}
.bite-card {border:2px solid #e0e0e0; border-radius:14px; padding:16px 18px;
            background:#fff; margin-bottom:8px;}
.bite-card h4 {margin:0 0 2px 0;}
.bite-tag {display:inline-block; padding:2px 10px; border-radius:20px;
           font-size:0.8rem; font-weight:600; margin:2px 4px 2px 0;}
.bite-explain {background:#f4f7f4; border-left:4px solid #2e7d32;
               padding:10px 12px; border-radius:6px; font-size:0.9rem;
               margin-top:10px;}
.bite-source {color:#666; font-size:0.78rem; margin-top:8px;}
.bite-nutri {font-size:0.86rem; margin:2px 0;}
.bite-img {text-align:center; margin:6px 0 4px 0;}
.bite-img img {border-radius:10px; max-height:130px; object-fit:contain;}
</style>
""", unsafe_allow_html=True)

# Grade -> (border colour, icon+letter label). Colour is never the only signal.
GRADE_STYLE = {
    "a": ("#1e8f4e", "🟢 A"), "b": ("#86b817", "🟢 B"),
    "c": ("#f6c700", "🟡 C"), "d": ("#ee8100", "🟠 D"),
    "e": ("#e63312", "🔴 E"),
    "a-plus": ("#1e8f4e", "🟢 A+"), "f": ("#a32000", "🔴 F"),
}
ROLE_COLOUR = {"🔍 You searched": "#1f77b4",
               "💚 Better for You": "#2e7d32",
               "🌍 Better for Earth": "#ee8100"}


# --------------------------------------------------------------------------- #
# Data (cached so loading + training happens once)
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner="Loading Open Food Facts data and training the model…")
def load_catalog():
    return biterec.build_catalog()


try:
    DF, MODEL = load_catalog()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
def radar_chart(searched, alts):
    fig = go.Figure()
    axes = scoring.RADAR_AXES + [scoring.RADAR_AXES[0]]

    def add(label, row, rgb, hexc):
        vals = scoring.radar_values(row)
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]], theta=axes, fill="toself",
            fillcolor=f"rgba({rgb},0.18)", line=dict(color=hexc, width=2),
            name=label, hovertemplate="<b>%{theta}</b>: %{r:.0f}/100<extra></extra>"))

    add(f"🔍 {searched.get(C.COL_NAME,'')[:22]}", searched, "31,119,180", "#1f77b4")
    pal = [("46,125,50", "#2e7d32"), ("238,129,0", "#ee8100")]
    for i, (lbl, row) in enumerate(alts):
        add(lbl, row, *pal[i % len(pal)])
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="center", x=0.5),
        height=430, margin=dict(t=30, b=70, l=40, r=40))
    return fig


def grade_distribution_chart(df):
    grades = list("abcde")
    letters = [g.upper() for g in grades]
    colours = [GRADE_STYLE[g][0] for g in grades]
    nutri = df["effective_grade"].value_counts()
    eco = df[C.COL_ECOSCORE_GRADE].value_counts()
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Nutri-Score", x=letters,
                         y=[int(nutri.get(g, 0)) for g in grades],
                         marker_color=colours,
                         text=[int(nutri.get(g, 0)) for g in grades],
                         textposition="outside"))
    fig.add_trace(go.Bar(name="Eco-Score", x=letters,
                         y=[int(eco.get(g, 0)) for g in grades],
                         marker_color=colours, opacity=0.45,
                         text=[int(eco.get(g, 0)) for g in grades],
                         textposition="outside"))
    fig.update_layout(barmode="group", height=330,
                      xaxis_title="Grade", yaxis_title="Number of products",
                      legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
                      margin=dict(t=20, b=50))
    return fig


def attribution_chart(attrib):
    if not attrib:
        return None
    items = sorted(attrib, key=lambda d: d["contribution"])
    feats = [d["label"].title() for d in items]
    vals = [d["contribution"] for d in items]
    colours = ["#e63312" if v < 0 else "#1e8f4e" for v in vals]
    fig = go.Figure(go.Bar(x=vals, y=feats, orientation="h", marker_color=colours,
                           hovertemplate="<b>%{y}</b>: %{x:.3f}<extra></extra>"))
    fig.update_layout(
        title=dict(text="Local feature attribution (this product's Nutri-Score)<br>"
                        "<sup>🟢 helps the score · 🔴 hurts the score</sup>",
                   font=dict(size=13)),
        xaxis_title="Contribution", height=320,
        margin=dict(l=20, r=20, t=70, b=30),
        xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor="#888"))
    return fig


def importance_chart(model):
    imp = sorted(model.feature_importance.items(), key=lambda x: x[1])
    feats = [C.FEATURE_LABELS[k].title() for k, _ in imp]
    vals = [v for _, v in imp]
    fig = go.Figure(go.Bar(x=vals, y=feats, orientation="h", marker_color="#2e7d32",
                           hovertemplate="<b>%{y}</b>: %{x:.3f}<extra></extra>"))
    fig.update_layout(title=dict(text="Global feature importance (Random Forest)",
                                 font=dict(size=13)),
                      xaxis_title="Importance", height=320,
                      margin=dict(l=20, r=20, t=50, b=30))
    return fig


# --------------------------------------------------------------------------- #
# Card rendering (with product image + nutrient detail)
# --------------------------------------------------------------------------- #
def _num(v, unit=""):
    if pd.isna(v):
        return "n/a"
    return f"{float(v):.1f}{unit}".replace(".0" + unit, unit) if unit else f"{float(v):.1f}"


def grade_tag(grade, prefix):
    g = str(grade).strip().lower()
    if g in GRADE_STYLE:
        col, lab = GRADE_STYLE[g]
        return (f"<span class='bite-tag' style='background:{col}22;color:{col};"
                f"border:1px solid {col}'>{prefix}: {lab}</span>")
    return f"<span class='bite-tag' style='background:#eee;color:#666'>{prefix}: ❔ n/a</span>"


def render_card(product, *, role, explanation=None):
    name = product.get(C.COL_NAME, "Unknown product")
    brand = product.get(C.COL_BRANDS, "")
    border = ROLE_COLOUR.get(role, "#e0e0e0")
    predicted = bool(product.get("grade_is_predicted", False))
    img = str(product.get(C.COL_IMAGE, "") or "").strip()

    st.markdown(
        f"<div class='bite-card' style='border-color:{border}'>"
        f"<div style='color:{border};font-weight:700'>{role}</div>"
        f"<h4>{name}</h4>"
        + (f"<small style='color:#666'>{brand}</small>" if brand else "") +
        "<div style='margin-top:6px'>"
        + grade_tag(product.get("effective_grade", ""), "Nutrition")
        + grade_tag(product.get(C.COL_ECOSCORE_GRADE, ""), "Eco")
        + "</div></div>", unsafe_allow_html=True)

    if img.startswith("http"):
        st.markdown(f"<div class='bite-img'><img src='{img}'/></div>",
                    unsafe_allow_html=True)

    if predicted:
        st.caption("ℹ️ Nutri-Score estimated by the ML model from nutrient values.")

    # Nutrient detail grid (per 100 g).
    cols = st.columns(2)
    nut_left = [("⚡", "Energy", product.get("energy-kcal_100g"), " kcal"),
                ("💪", "Protein", product.get("proteins_100g"), " g"),
                ("🌾", "Fibre", product.get("fiber_100g"), " g")]
    nut_right = [("🍬", "Sugar", product.get("sugars_100g"), " g"),
                 ("🧈", "Fat", product.get("fat_100g"), " g"),
                 ("🧂", "Salt", product.get("salt_100g"), " g")]
    for col, group in zip(cols, (nut_left, nut_right)):
        with col:
            for icon, lbl, val, unit in group:
                col.markdown(f"<div class='bite-nutri'>{icon} <b>{lbl}:</b> "
                             f"{_num(val, unit)}</div>", unsafe_allow_html=True)

    # Concrete eco metrics (FR-08) — framed as facts, never guilt (NFR-04).
    eco = scoring.concrete_eco_metrics(product)
    if "car_km_equivalent" in eco:
        st.markdown(f"<div class='bite-nutri'>🚗 ~{eco['car_km_equivalent']} km of car "
                    f"driving per 100 g <small>(est. {eco['co2_kg_per_100g']} kg CO₂e)</small>"
                    f"</div>", unsafe_allow_html=True)
    if eco.get("origin"):
        st.markdown(f"<div class='bite-nutri'>📍 Origin: {eco['origin']}</div>",
                    unsafe_allow_html=True)
    if eco.get("labels"):
        st.markdown(f"<div class='bite-nutri'>🏷️ {eco['labels']}</div>",
                    unsafe_allow_html=True)

    if explanation:
        st.markdown(f"<div class='bite-explain'>💡 {explanation}</div>",
                    unsafe_allow_html=True)

    url = product.get(C.COL_URL, "") or C.DATA_SOURCE_URL
    st.markdown(f"<div class='bite-source'>📦 <a href='{url}' target='_blank'>"
                f"View on {C.DATA_SOURCE_NAME}</a></div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Sidebar — preferences (no login required, FR-10)
# --------------------------------------------------------------------------- #
COMMON_ALLERGENS = ["milk", "eggs", "gluten", "peanuts", "nuts", "soybeans",
                    "fish", "crustaceans", "sesame", "mustard", "celery"]

with st.sidebar:
    st.header("⚙️ Your preferences")
    st.caption("No account needed. Settings apply to this session.")

    health_pct = st.slider("Priority: Health ⟷ Environment", 0, 100,
                           int(C.DEFAULT_HEALTH_WEIGHT * 100),
                           help="Default 70 % health reflects our user research "
                                "(6 of 8 participants prioritised health).")
    st.caption(f"⚖️ **{health_pct}% health · {100 - health_pct}% environment**")
    health_weight = health_pct / 100

    st.divider()
    st.subheader("🚫 Allergens (hard filter)")
    st.caption("Products containing these are never recommended.")
    picked = st.multiselect("Common allergens", COMMON_ALLERGENS)
    extra = st.text_input("Other (comma-separated)", placeholder="e.g. lupin, walnut")
    allergens = picked + [a.strip() for a in extra.split(",") if a.strip()]

    st.divider()
    st.subheader("🔎 Refine alternatives")
    quick = {
        "high_protein": st.checkbox("💪 High protein (≥10 g)"),
        "low_sugar": st.checkbox("🍬 Low sugar (≤5 g)"),
        "low_salt": st.checkbox("🧂 Low salt (≤0.3 g)"),
        "organic": st.checkbox("🌱 Organic label"),
    }
    with st.expander("🔬 Advanced nutrient sliders"):
        quick["min_protein"] = st.slider("Min protein (g/100g)", 0, 30, 0)
        quick["max_sugar"] = st.slider("Max sugar (g/100g)", 0, 100, 100)
        quick["max_salt"] = st.slider("Max salt (g/100g)", 0.0, 10.0, 10.0, 0.1)
        quick["max_fat"] = st.slider("Max fat (g/100g)", 0, 100, 100)
    filters = quick

    st.divider()
    st.caption(f"Model accuracy: **{MODEL.accuracy:.0%}** "
               f"(trained on {MODEL.n_train} labelled products). "
               f"Data: {C.DATA_SOURCE_NAME}.")


# --------------------------------------------------------------------------- #
# Header + search (FR-01)
# --------------------------------------------------------------------------- #
st.title("🥗 BiteRec")
st.markdown("**Transparent food recommendations** balancing nutrition and "
            "environmental impact — with an explanation for every suggestion.")

query = st.text_input("Search for a food product",
                      placeholder="whole milk, chocolate, yogurt…")

# --------------------------------------------------------------------------- #
# Welcome screen (no query yet): database overview + nicer chart
# --------------------------------------------------------------------------- #
if not query:
    scorable = int(DF["is_scorable"].sum())
    predicted = int(DF["grade_is_predicted"].sum())
    both = int((DF["health_score"].notna() & DF["eco_score"].notna()).sum())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Products loaded", f"{len(DF):,}")
    m2.metric("Scorable products", f"{scorable:,}")
    m3.metric("Grades filled by ML", f"{predicted:,}")
    m4.metric("Health + eco scored", f"{both:,}")
    st.markdown("#### Score distribution in the database")
    st.plotly_chart(grade_distribution_chart(DF), use_container_width=True)
    st.info("👆 Search for a product to see a healthier and a greener alternative, "
            "each with a picture, a plain-language reason and an interactive comparison.")
    st.stop()

matches = recommender.search_products(DF, query)
if matches.empty:
    st.warning(f"No product matching “{query}” was found. Try a more general term "
               f"(e.g. *milk*, *bread*, *juice*).")
    st.stop()

labels = [f"{r[C.COL_NAME]}" + (f" — {r[C.COL_BRANDS]}" if r[C.COL_BRANDS] else "")
          for _, r in matches.iterrows()]
choice = st.selectbox("Matching products", range(len(labels)),
                      format_func=lambda i: labels[i])
searched = matches.iloc[choice]

if not searched["is_scorable"]:
    st.warning("This product has too little nutritional data to score reliably. "
               "Pick another match above.")
    st.stop()

rec = recommender.recommend(DF, searched, health_weight, allergens, filters)
alts = [(lbl, rec[key]) for key, lbl in
        [("better_health", "💚 Better for You"), ("better_eco", "🌍 Better for Earth")]
        if rec[key] is not None]

# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
tab_rec, tab_ai = st.tabs(["📊 Recommendations", "🤖 AI Details"])

with tab_rec:
    if rec.get("primary_is_winwin"):
        p = rec["primary"]
        st.success(f"🌟 Win-win pick: **{p[C.COL_NAME]}** scores better on *both* "
                   f"nutrition and environment than your search.")

    c1, c2, c3 = st.columns(3)
    with c1:
        render_card(searched, role="🔍 You searched")
    with c2:
        if rec["better_health"] is not None:
            render_card(rec["better_health"], role="💚 Better for You",
                        explanation=explainer.explain_alternative(
                            rec["better_health"], searched, "health"))
        else:
            st.info("No nutritionally better option found in this category "
                    "with your current filters.")
    with c3:
        if rec["better_eco"] is not None:
            render_card(rec["better_eco"], role="🌍 Better for Earth",
                        explanation=explainer.explain_alternative(
                            rec["better_eco"], searched, "eco"))
        else:
            st.info("No ecologically better option found in this category "
                    "with your current filters.")

    st.caption(f"Compared against {rec['pool_size']} products in the same category. "
               f"All data from {C.DATA_SOURCE_NAME}.")

    if alts:
        st.markdown("#### 🕸️ Multi-dimensional comparison")
        st.caption("Each axis runs 0–100; further out is better.")
        st.plotly_chart(radar_chart(searched, alts), use_container_width=True)

with tab_ai:
    st.markdown("### Why these recommendations? (Explainable AI)")
    a, b, c = st.columns(3)
    a.metric("Model", "Random Forest")
    b.metric("Accuracy", f"{MODEL.accuracy:.0%}")
    c.metric("Trained on", f"{MODEL.n_train} products")

    left, right = st.columns(2)
    with left:
        st.plotly_chart(importance_chart(MODEL), use_container_width=True)
    with right:
        attrib = explainer.feature_attribution(searched, MODEL)
        chart = attribution_chart(attrib[:7])
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.caption("Not enough nutrient data for local attribution.")

    if alts:
        st.markdown("#### Side-by-side: recommended vs your search")
        st.caption("Contrastive explanation — *why this rather than your usual choice?*")
        cdf = pd.DataFrame(explainer.contrast(alts[0][1], searched))
        st.dataframe(cdf.rename(columns={
            "dimension": "Dimension", "recommended": "Recommended",
            "yours": "Your search", "unit": "Unit", "favours": "Favours"}),
            hide_index=True, use_container_width=True)
    st.caption(f"Every figure is sourced from {C.DATA_SOURCE_NAME}. "
               "CO₂ values are estimates derived from the Eco-Score grade.")

st.divider()
st.caption("BiteRec · HCI 2026 project prototype · Data © Open Food Facts "
           "contributors (ODbL). CO₂ figures are illustrative estimates.")
