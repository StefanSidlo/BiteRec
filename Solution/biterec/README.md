# BiteRec — Transparent Multi-Objective Food Recommendations

BiteRec is a web platform that helps people choose foods that are **better for their health**
*and* **better for the planet**, and — crucially — it **explains why** in plain language. For
any product you look at, it surfaces a *Better for You* alternative, a *Better for Earth*
alternative, and (when one exists) a single *Best overall* pick, each backed by an explanation,
contrastive deltas, and radar charts.

It is built on real [Open Food Facts](https://world.openfoodfacts.org/) data, a small
machine-learning model for the health dimension, and a transparent scoring layer for the
ecological dimension.

---

## Quick start

```bash
# 1. (optional) create a virtual environment
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. (optional) rebuild the dataset from a raw Open Food Facts CSV
#    A pre-built data/products.json is already included, so you can skip this.
python build_data.py

# 4. run the app
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

> The app ships with a pre-built `data/products.json`, so step 3 is **optional** — it only needs
> to be re-run if you want to regenerate the dataset (e.g. from the full Open Food Facts dump).

To set a stable session secret (recommended for the live demo) export `BITEREC_SECRET`
before launching:

```bash
export BITEREC_SECRET="any-long-random-string"   # Windows: set BITEREC_SECRET=...
python app.py
```

---

## What's in the box

```
biterec/
├── app.py              # Flask server + JSON API
├── recommender.py      # ML health model + eco scoring + recommendation/XAI logic
├── auth.py             # File-based user accounts (no database)
├── build_data.py       # Cleans ANY Open Food Facts CSV → data/products.json
├── requirements.txt
├── data/
│   ├── products.json   # pre-built, cleaned dataset (committed, app runs on this)
│   ├── users.json      # created at runtime (git-ignored)
│   └── *.csv           # raw Open Food Facts export (input to build_data.py)
├── templates/
│   └── index.html      # single-page app shell
└── static/
    ├── css/styles.css  # calm-green, colour-blind-safe, responsive theme
    └── js/
        ├── app.js      # UI controller (search, filters, account, charts)
        └── charts.js   # Chart.js radar / bar / doughnut helpers
```

---

## Architecture

**Backend — Flask (Python).** Chosen over Streamlit/Dash so we have full control over the
Google-style autocomplete, search history, custom tooltips, mobile layout, and the green theme.
The recommender model is trained **once** at startup and held in memory; every request is served
from the in-memory dataset, so responses are well under the 3-second target.

**Frontend — vanilla HTML/CSS/JS + Chart.js.** A single-page app talks to a small JSON API.
No build step, no framework — easy to read, present, and extend.

**Data — pre-cleaned JSON.** `build_data.py` does the heavy cleaning once and writes
`data/products.json`; the running app never touches the raw CSV.

### The two objectives

| Dimension | How it is computed |
|-----------|--------------------|
| **Health** | A `RandomForestClassifier` (120 trees) trained on 7 nutrients — energy, sugars, fat, saturated fat, proteins, salt, fibre — to predict the Nutri-Score grade. We turn the class probabilities into a **continuous 0–100 health score** so products can be ranked finely, not just bucketed into A–E. Honest accuracy is reported with **5-fold cross-validation** (a plain train-fit score would be a misleading ~100%). |
| **Ecology** | Uses the **real Open Food Facts environmental score** (0–100) directly, so the ranking reflects actual data; plus **estimated** CO₂ and water footprints (see note below). |

The user's **priority slider** blends the two into a single combined score
(default **70 % health / 30 % eco**, per FR-03).

### Explainability (XAI)

* **SHAP feature attribution, two readable views.** A `shap.TreeExplainer` decomposes every
  prediction (the approach from `off_nutriscore_01.ipynb` §5). The headline view projects SHAP onto a
  single 0–100 health axis (average product → this product, green helps / red hurts). An expandable
  **per-grade probability waterfall** with a grade selector shows, for any chosen Nutri-Score grade
  A–E, how each nutrient raises or lowers the model's probability of *that* grade — the exact
  interaction from the notebook and the Streamlit prototype's "Explain probability of grade" dropdown.
* **Global importance on the Insights page.** Both the Random-Forest feature importance *and* the
  SHAP global importance (mean |φ| per nutrient across the catalogue) are charted, with a
  plain-language "how the model works" note.
* **Contrastive comparison tables.** On the recommendation screen, each alternative gets a
  Yours-vs-Alternative table (Nutri/Eco grade, energy, protein, sugar, salt, fat, fibre, CO₂).
* **Plain-language explanations** (≤2 sentences, FR-06) and **radar profiles** (nutrition + ecology)
  live on each product's **detail page**.

---

## How it meets the requirements

| Req | Where |
|-----|-------|
| **FR-01** Search without login | `/api/search`, `/api/suggest` — no auth required |
| **FR-02** Multi-criteria filtering | Live client-side filters in `app.js` (`passesFilters`) |
| **FR-03** Priority slider (default 70/30) | Slider in UI → `w` param → `recommend(w_health=0.7)` |
| **FR-04** Allergens as a hard constraint | Allergen-flagged products removed **before** scoring in `recommend()` |
| **FR-05** Two alternatives | `better_you` + `better_earth`; or, if you enable only one in Account, your top-3 ranked picks for that goal |
| **FR-06** Plain-language explanations (≤2 sentences) | `_explain()` in `recommender.py` |
| **FR-07** Radar chart over 5–6 dimensions | 3 radars built by `_radar_dims` / `nutrition_radar` / `eco_radar` |
| **FR-08** Eco metrics in concrete units | CO₂ in kg, water in litres, plus "≈ km driven by car" |
| **FR-09** Data-source transparency | Every product links back to its Open Food Facts page; footer attribution |
| **FR-10** No mandatory registration | Login is optional; only needed to save preferences/favourites |

**Non-functional:** responses are in-memory and fast (< 3 s); grades are shown as **letter +
colour together** (never colour alone) so they remain readable for colour-blind users; copy is
neutral and non-moralising.

> **Note on login (FR-01 / FR-10).** This build **requires an account** to use the platform, as
> requested for the demo. That deliberately overrides the original FR-01 ("search without login")
> and FR-10 ("no mandatory registration") from the requirements document. If your report needs to
> honour FR-01/FR-10 instead, it's a one-line change: in `static/js/app.js`, the `go()` function
> contains the gate (`if (gated() && view !== 'account')`) — remove that block and the platform is
> usable without signing in again.

### Feature checklist

User login (file-based, **required**) · account page for allergens (preset chips **+ free-text
typing**), health/eco priority, **and toggles to show the healthier and/or greener alternative**
(enable one to get its top-3 ranked) · save favourites · Google-style autocomplete · live-updating
quick filters · **product detail pages** with real **ingredients**, an **environment panel** (real
Eco-Score + estimated carbon), nutrition/ecology radars, and the SHAP breakdown · dataset +
**model-insight** dashboard with RF and SHAP global importance · mobile / responsive layout ·
recent-search history · help tooltips · SHAP "why this grade" waterfall **with per-grade selector**
· contrastive comparison tables · product photos · calm-green UI · cleaned generic dataset using the
**real numeric Eco-Score** for ranking.

---

## Working with a different / larger dataset

`build_data.py` accepts **any** Open Food Facts CSV export (tab-separated). It:

* keeps only products that have a name, a valid Nutri-Score grade, a valid Eco-Score grade, and
  the four core nutrients (so recommendations are meaningful for the demo);
* imputes missing optional nutrients to 0 and sanity-clips per-100 g values;
* derives **allergen flags** from the ingredients text (the raw allergen column is essentially
  empty), covering the main EU allergens;
* **estimates** CO₂ and water footprints per category (the raw carbon column is essentially
  empty);
* de-duplicates by name + brand.

To use the full dump, download it from Open Food Facts and pass the path as an argument:

```bash
python build_data.py path/to/your_openfoodfacts_export.csv
```

With no argument it defaults to the bundled `data/openfoodfacts_short_30MB.csv`.

---

## Important caveats (please mention in the demo)

* **Eco footprints are estimates.** The raw Open Food Facts carbon/water columns were almost
  entirely empty, so CO₂ and water figures are *derived from category baselines adjusted by the
  Eco-Score grade*. They illustrate relative differences, not certified life-cycle values, and
  the UI labels them as estimates.
* **Model accuracy is the 5-fold cross-validation score**, which is the honest generalisation
  estimate — not the (near-perfect, overfit) training-set score.
* The bundled dataset is a **few hundred well-populated products** chosen for a snappy, sensible
  live demo. `build_data.py` scales to the full Open Food Facts dump if you want more.

---

## Data & attribution

Product data from **Open Food Facts**, available under the
[Open Database License](https://opendatacommons.org/licenses/odbl/1-0/). Individual product
contents are under the Database Contents License. Product images are © Open Food Facts
contributors. This project is for educational use.
