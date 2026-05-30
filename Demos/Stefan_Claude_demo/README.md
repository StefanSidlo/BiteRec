# 🥗 BiteRec — Transparent Multi-Objective Food Recommendations

BiteRec is a web platform that recommends food products by balancing **two
goals at once**: how good a product is for **you** (nutrition) and how good it
is for the **planet** (environmental footprint). For every product you search,
it surfaces a *Better for You* and a *Better for Earth* alternative — and, most
importantly, it **explains every recommendation in plain language**.

Built for the HCI 2026 course project *"Transparent Multi-Objective Food
Recommendations"*, using the [Open Food Facts](https://world.openfoodfacts.org)
database and a machine-learning model for Nutri-Score prediction and
explainability.

---

## ✨ What it does

| Feature | Requirement | Description |
|---|---|---|
| 🔎 Product search | FR-01 | Search any food product by name. No login required. |
| 🖼️ Product images | — | Cards show the product photo (from Open Food Facts) plus a per-100 g nutrient breakdown. |
| 🎚️ Priority slider | FR-03 | Set your personal health ⟷ environment weighting (default **70 % health**, from our user research). |
| 🚫 Allergen hard-filter | FR-04 | Pick from common allergens or type your own; matches are **never** recommended. |
| 🔀 Two alternatives | FR-05 | Every search returns a healthier and a greener option; win-win picks are highlighted. |
| 💡 XAI explanations | FR-06 | Each recommendation has a one/two-sentence reason citing concrete attributes. |
| 🕸️ Radar chart | FR-07 | Interactive 6-dimension comparison (Nutri-Score, Eco-Score, protein, sugar, salt, CO₂). |
| 🚗 Concrete eco-metrics | FR-08 | Environmental impact shown as *"~X km of car driving per 100 g"*, never as an abstract number. |
| 🔗 Source transparency | FR-09 | Every figure links back to its Open Food Facts source. |
| 🎛️ Multi-criteria filters | FR-02 | Quick toggles **and** advanced sliders (min protein, max sugar/salt/fat) + organic. |
| 📊 Database overview | — | Home screen shows live stats and a Nutri-/Eco-Score distribution chart. |
| 🤖 AI Details tab | FR-06 | Global feature importance, local feature-attribution chart, and a contrastive comparison table. |

The interface follows the project's non-functional rules: colour is always
paired with an **icon + text label** (accessibility), the results screen is
**scannable in seconds**, and the language is always **gain-framed, never
guilt-inducing**. The app is organised into two tabs — **📊 Recommendations**
(cards, images, radar) and **🤖 AI Details** (model insight, attribution,
contrastive comparison).

---

## 🤖 The machine learning

The data export leaves the **Nutri-Score blank ("unknown") for ~80 % of
products**. BiteRec trains a **Random Forest classifier** (following the team's
`off_nutriscore_01.ipynb` notebook) to predict the Nutri-Score grade (A–E) from
seven nutrient values (energy, sugar, fat, saturated fat, protein, salt, fibre).

This serves two purposes:

1. **Coverage** — the model fills in missing grades so far more products become
   recommendable (roughly **doubling** the scorable catalogue).
2. **Explainability (XAI)** — the trained model exposes feature importances,
   and BiteRec computes a per-product nutrient **attribution** ("✅ helps /
   ⚠️ hurts the score") that powers the explanations and the *Why is this
   recommended?* panel.

The model trains automatically on first launch (a few seconds) and is cached to
`models/nutriscore_rf.joblib`.

---

## 🚀 Getting started

You need **Python 3.10+**.

### Option A — one command (recommended)

```bash
# macOS / Linux
./run.sh

# Windows (double-click run.bat, or:)
run.bat
```

The launcher installs dependencies on first run and opens the app in your
browser at `http://localhost:8501`.

### Option B — run as a program

```bash
pip install -r requirements.txt
python run.py
```

### Option C — standard Streamlit command

```bash
pip install -r requirements.txt
streamlit run app.py
```

> 💡 Tip: a virtual environment keeps things clean —
> `python -m venv .venv && source .venv/bin/activate` (Windows:
> `.venv\Scripts\activate`).

---

## 🗂️ Project structure

```
biterec/
├── app.py                 # Streamlit web app (frontend)
├── run.py / run.sh / run.bat
├── requirements.txt
├── data/
│   └── openfoodfacts_short.csv   # Open Food Facts export (tab-delimited)
├── models/                # cached trained model (auto-generated)
├── .streamlit/config.toml # theme
└── biterec/               # backend package
    ├── config.py          # column names, scoring maps, constants
    ├── data_loader.py     # load + clean + clip the OFF CSV
    ├── ml_model.py        # Random Forest Nutri-Score model
    ├── scoring.py         # health/eco/combined scores, CO₂ estimate, radar
    ├── recommender.py     # search, allergen filter, alternative engine
    └── explainer.py       # XAI: explanations, attribution, contrast
```

---

## 🧱 How it works (data flow)

```
CSV ──▶ data_loader (clean, clip) ──▶ ml_model (train / predict grades)
                                          │
                                          ▼
                          scoring (health, eco, combined, CO₂)
                                          │
                  search ──▶ recommender (category pool, allergen filter,
                                          Better-for-You / Better-for-Earth)
                                          │
                                          ▼
                          explainer (plain-language reason, radar, attribution)
                                          │
                                          ▼
                                    app.py (Streamlit UI)
```

---

## 📊 The data

- Source: **Open Food Facts** (`data/openfoodfacts_short.csv`), a tab-delimited
  export of ~12 k products. Licensed under the
  [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).
- To use the **full** database, download the export from
  [Open Food Facts data](https://world.openfoodfacts.org/data), drop it in
  `data/`, and name it `openfoodfacts.csv` (or update `CSV_CANDIDATES` in
  `biterec/config.py`).

> ⚠️ **Note on CO₂ figures.** Open Food Facts rarely fills the raw
> carbon-footprint field, so BiteRec derives an **estimated** CO₂ value from the
> Eco-Score grade purely to produce relatable "concrete unit" comparisons. These
> are illustrative, not measured values, and are always labelled as estimates in
> the UI.

---

## 👥 Team

HCI 2026 project — Jan Kuca, Stefan Sidlovsky, Anna Maria Chovancova,
Alvaro Velasco Sobrino.

Design decisions (the 70/30 default, the no-moralising framing, the demand for
explanations and source transparency) come directly from the team's user
research report.

---

## 🧭 Roadmap / ideas

- Optional account to persist preferences across sessions (FR-10, optional part).
- Replace the Eco-Score-based CO₂ proxy with real LCA data when available.
- Add the System Usability Scale + Explanation Satisfaction survey for the
  evaluation phase.
- Richer category matching once the full OFF export (with denser categories) is
  used.
