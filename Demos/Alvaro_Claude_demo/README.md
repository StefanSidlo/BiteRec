# 🥗 BiteRec — Transparent Multi-Objective Food Recommendations

> HCI 2026 course project — *"Transparent Multi-Objective Food Recommendations"*  
> Jan Kuca · Stefan Sidlovsky · Anna Maria Chovancova · Alvaro Velasco Sobrino

BiteRec is a web platform that recommends food products by balancing **two goals at once**: how good a product is for **you** (nutrition) and how good it is for the **planet** (environmental footprint). For every product you search, it surfaces a *Better for You* and a *Better for Earth* alternative — and, most importantly, it **explains every recommendation in plain language**.

Built with [Open Food Facts](https://world.openfoodfacts.org) data and a Random Forest + SHAP machine learning pipeline.

---

## ✨ Features

| Feature | Requirement | Description |
|---|---|---|
| 🔎 Product search | FR-01 | Search any food product by name. No login required. |
| 🎚️ Priority slider | FR-03 | Set your personal health ↔ planet weighting (default **70% health** from user research). |
| 🚫 Allergen hard-filter | FR-04 | Pick common allergens or type custom ones — matches are **never** recommended. |
| 🔀 Two alternatives | FR-05 | Every search returns a healthier and a greener option; win-win picks are highlighted. |
| 💡 XAI explanations | FR-06 | Each recommendation has a plain-language reason citing concrete attributes. |
| 🕸️ Radar chart | FR-07 | Interactive 6-dimension comparison (Nutri-Score, Eco-Score, protein, sugar, salt, CO₂). |
| 🚗 Concrete eco-metrics | FR-08 | Environmental impact shown as *"~X km of car driving per 100 g"*, never as an abstract score. |
| 🔗 Source transparency | FR-09 | Every figure links back to its Open Food Facts source. |
| 🎛️ Advanced filters | FR-02 | Sliders for min protein, max sugar/salt + organic toggle. |
| 🤖 AI Details tab | FR-06 | SHAP waterfall plot, global feature importance, and contrastive comparison table. |

The interface follows the project's non-functional requirements: colour is always paired with an **icon + text label** (NFR-02 accessibility), the results screen is **scannable in seconds** (NFR-03), and all language is **gain-framed, never guilt-inducing** (NFR-04).

---

## 🤖 Machine Learning

The Open Food Facts export leaves the Nutri-Score blank for ~80% of products. BiteRec trains a **Random Forest classifier** to predict the Nutri-Score grade (A–E) from seven nutrient values (energy, sugar, fat, saturated fat, protein, salt, fibre), roughly doubling the number of recommendable products.

**Explainability (XAI)** is powered by [SHAP TreeExplainer](https://shap.readthedocs.io), following the methodology in `off_nutriscore_01.ipynb`:
- **Global importance** — mean |SHAP| per feature across the dataset
- **Local waterfall** — per-product explanation showing exactly which nutrients pushed the prediction up or down

---

## 🚀 Getting Started

### Requirements

- Python 3.10+
- ~4 GB RAM (for the filtered dataset)
- The Open Food Facts CSV (see [Data](#-data) below)

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/your-username/biterec.git
cd biterec

# 2. Install dependencies
pip install -r requirements.txt

# 3. Place the dataset (see Data section below)
# data/en.openfoodfacts.org.products.csv

# 4. Launch
streamlit run app.py
```

Or use the one-command launchers:

```bash
# macOS / Linux
./run.sh

# Windows
run.bat
```

The app opens automatically at `http://localhost:8501`.  
**First launch takes a few minutes** — it filters the dataset, trains the model, and builds the search index. Everything is cached after that.

---

## 📊 Data

**Source:** [Open Food Facts](https://world.openfoodfacts.org/data) — a free, open database of food products worldwide. Licensed under the [Open Database Licence (ODbL)](https://opendatacommons.org/licenses/odbl/).

**Download:** Go to the [Open Food Facts data page](https://world.openfoodfacts.org/data), download the CSV export (`en.openfoodfacts.org.products.csv`, ~9 GB), and place it in the `data/` folder:

```
biterec/
└── data/
    └── en.openfoodfacts.org.products.csv   ← place it here
```

The app also accepts `data/openfoodfacts.csv` or `data/openfoodfacts_short.csv` (configured in `biterec/config.py`).

> ⚠️ **Note on CO₂ figures.** The OFF export rarely includes measured carbon footprint data, so BiteRec derives an **estimated** CO₂ value from the Eco-Score grade to produce relatable concrete comparisons. These are illustrative, not measured values, and are always labelled as estimates in the UI.

> ⚠️ **Note on Eco-Score.** The downloadable OFF CSV has very sparse Eco-Score coverage (~0%). Recommendations still work using the CO₂ proxy, but the Eco-Score A–E grade will show as unknown for most products.

---

## 🗂️ Project Structure

```
biterec/
├── app.py                        # Streamlit web app (UI)
├── run.py / run.sh / run.bat     # One-command launchers
├── requirements.txt
│
├── data/                         # Place the OFF CSV here (not tracked by git)
├── models/                       # Cached trained model (auto-generated, not tracked)
│
├── .streamlit/
│   └── config.toml               # Theme
│
└── biterec/                      # Backend Python package
    ├── __init__.py
    ├── config.py                 # Column names, scoring maps, constants
    ├── data_loader.py            # DuckDB-powered CSV loader + cleaning pipeline
    ├── ml_model.py               # Random Forest + SHAP explainer
    ├── scoring.py                # Health / eco / combined scores, CO₂ estimation
    ├── recommender.py            # Search index, allergen filter, alternative engine
    └── explainer.py              # XAI: plain-language reasons, SHAP helpers, contrastive table
```

---

## 🧱 Architecture

```
CSV ──▶ data_loader (DuckDB query → clean → filter)
              │
              ▼
        ml_model (train RF / load cache → predict missing Nutri-Scores)
              │
              ▼
        scoring (health_score, eco_score_val, co2_g_per_100g — computed once)
              │
              ▼
        search_index (pre-lowercased Series — built once at startup)
              │
    search ──▶ recommender (category pool → allergen filter → idxmax picks)
              │
              ▼
        explainer (plain-language text, SHAP waterfall, contrastive table)
              │
              ▼
           app.py (Streamlit UI — tabs, cards, radar chart, slider)
```

---

## ⚙️ Configuration

All tuneable parameters are in `biterec/config.py`:

| Parameter | Default | Description |
|---|---|---|
| `DEFAULT_HEALTH_WEIGHT` | `0.70` | Slider default (70% health / 30% eco) |
| `CSV_CANDIDATES` | see file | CSV paths tried in order |
| `HEALTH_WEIGHTS` | see file | Sub-component weights for health score |
| `ECO_WEIGHTS` | see file | Sub-component weights for eco score |
| `COMMON_ALLERGENS` | see file | Allergen keyword mappings |
| `MAX_SEARCH_RESULTS` | `50` | Max products shown in search dropdown |

---

## 👥 Team

HCI 2026 — Jan Kuca, Stefan Sidlovsky, Anna Maria Chovancova, Alvaro Velasco Sobrino.

Design decisions (the 70/30 default, no-moralising framing, demand for explanations and source transparency) come directly from the team's user research report (8 participants, 3 personas: Maya Kolsky, Adrien Dawin, Simon Joen).

---

## 📄 Licence

Code: [MIT](LICENSE)  
Data: Open Food Facts is licensed under the [Open Database Licence (ODbL)](https://opendatacommons.org/licenses/odbl/). Product images and facts are licensed under [CC BY-SA](https://creativecommons.org/licenses/by-sa/3.0/).
