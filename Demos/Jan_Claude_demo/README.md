# 🥗 BiteRec – Transparent Multi-Objective Food Recommendations

> A prototype web platform for the HCI course at UIB 2026.
> Built with Python (FastAPI) + vanilla HTML/CSS/JS.

---

## Features

| Feature | Implemented |
|---|---|
| Product search by name | ✅ |
| ML-powered alternatives (KNN cosine similarity) | ✅ |
| Priority slider: Health ↔ Eco | ✅ |
| Allergen hard constraints | ✅ |
| Nutritional filters (high protein, low sugar) | ✅ |
| Organic filter | ✅ |
| XAI plain-language explanations | ✅ |
| Radar/spider chart comparison | ✅ |
| Data source transparency (Open Food Facts link) | ✅ |
| No mandatory registration | ✅ |

---

## Quickstart

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Place the CSV

Copy `openfoodfacts_short_30MB.csv` into this folder (same directory as `run.py`).

### 3. Run

```bash
python run.py
```

Then open **http://localhost:8000** in your browser.

Alternatively, pass a custom CSV path:

```bash
python run.py /path/to/your/openfoodfacts_short_30MB.csv
```

Or set the environment variable:

```bash
BITREC_CSV=/path/to/file.csv uvicorn app:app --port 8000
```

---

## Project structure

```
bitrec/
├── app.py              # FastAPI backend + API endpoints
├── data_loader.py      # CSV loading, cleaning, normalisation
├── recommender.py      # ML engine (KNN) + XAI explanations
├── run.py              # One-command launcher
├── requirements.txt
├── README.md
└── frontend/
    └── index.html      # Single-page frontend (HTML + Chart.js)
```

---

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /api/search?q=milk` | Search products by name |
| `GET /api/recommend/{idx}?health_weight=0.7&allergens=nuts` | Get recommendations |
| `GET /api/stats` | Dataset statistics |
| `GET /docs` | Interactive Swagger UI |

---

## ML approach

The recommendation engine uses **k-Nearest Neighbours (cosine similarity)** from scikit-learn,
trained on normalised nutritional + eco features:

- `health_score` (from Nutri-Score grade)
- `eco_score` (from Eco-Score grade)
- Energy, protein, fat, saturated fat, sugars, fibre, salt

Among the nearest neighbours:
- **Better for You** = highest `health_score` (subject to allergen/filter constraints)
- **Better for Earth** = highest `eco_score` (subject to allergen/filter constraints)

XAI explanations compare delta values (protein +X g, sugar −Y g, grade improvement) in plain language.

---

## Data source

Open Food Facts – https://world.openfoodfacts.org  
Licensed under ODbL (Open Database License).
