"""
app.py  --  BiteRec web application
=====================================

Flask backend that serves the single-page UI and a small JSON API:

  GET  /                         -> the app
  GET  /api/overview             -> dataset-wide stats for the insights view
  GET  /api/suggest?q=           -> autocomplete suggestions
  GET  /api/search?q=            -> full search results
  GET  /api/product/<id>         -> one product (with nutrition + eco radars)
  GET  /api/recommend/<id>?w=&allergens=  -> the two-alternative engine
  POST /api/register             -> create an account
  POST /api/login                -> sign in (session cookie)
  POST /api/logout               -> sign out
  GET  /api/me                   -> current profile (allergens, weight, favs)
  POST /api/preferences          -> save allergens + priority weight
  POST /api/favorite             -> toggle a favourite product

Run locally:
    pip install -r requirements.txt
    python build_data.py          # once, to generate data/products.json
    python app.py                 # then open http://127.0.0.1:5000
"""

import os
from flask import Flask, jsonify, request, session, render_template

import auth
from recommender import Recommender

app = Flask(__name__)
app.json.sort_keys = False  # keep our importance-sorted dicts in order
app.secret_key = os.environ.get("BITEREC_SECRET", "biterec-dev-secret-change-me")

# Load the catalog + ML model once at startup.
REC = Recommender()


def current_user():
    return session.get("user")


# --------------------------------------------------------------------- pages
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------- data
@app.route("/api/overview")
def api_overview():
    return jsonify(REC.overview())


@app.route("/api/suggest")
def api_suggest():
    return jsonify(REC.suggest(request.args.get("q", ""), limit=8))


@app.route("/api/search")
def api_search():
    return jsonify(REC.search(request.args.get("q", ""), limit=24))


@app.route("/api/product/<int:pid>")
def api_product(pid):
    p = REC.get(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    full = REC.by_id[pid]
    p["radar"] = full["radar"]
    p["nutrition_radar"] = REC.nutrition_radar(full)
    p["eco_radar"] = REC.eco_radar(full)
    p["attribution"] = REC._attribution(full)
    return jsonify(p)


@app.route("/api/detail/<int:pid>")
def api_detail(pid):
    d = REC.detail(pid)
    if not d:
        return jsonify({"error": "not found"}), 404
    return jsonify(d)


@app.route("/api/recommend/<int:pid>")
def api_recommend(pid):
    try:
        w = float(request.args.get("w", 0.7))
    except ValueError:
        w = 0.7
    w = max(0.0, min(1.0, w))
    allergens = [a for a in request.args.get("allergens", "").split(",") if a]
    sh = request.args.get("sh", "1") != "0"
    se = request.args.get("se", "1") != "0"

    # Soft filters (checkboxes + numeric sliders + min grades) so the
    # recommendation reacts live to the filter sidebar, just like the results.
    def _num(key):
        v = request.args.get(key)
        try:
            return float(v) if v not in (None, "") else None
        except ValueError:
            return None
    checks = set(c for c in request.args.get("f", "").split(",") if c)
    filters = {
        "high_protein": "high_protein" in checks, "low_sugar": "low_sugar" in checks,
        "low_salt": "low_salt" in checks, "low_satfat": "low_satfat" in checks,
        "high_fibre": "high_fibre" in checks, "low_calorie": "low_calorie" in checks,
        "low_co2": "low_co2" in checks, "organic": "organic" in checks,
        "few_additives": "few_additives" in checks,
        "minNutri": (request.args.get("minNutri") or "").lower() or None,
        "minEco": (request.args.get("minEco") or "").lower() or None,
        "max_sugar": _num("max_sugar"), "min_protein": _num("min_protein"),
        "max_salt": _num("max_salt"), "max_satfat": _num("max_satfat"),
        "max_energy": _num("max_energy"), "min_fibre": _num("min_fibre"),
    }
    result = REC.recommend(pid, w_health=w, allergens=allergens,
                           show_health=sh, show_eco=se, filters=filters)
    if result is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)


# ---------------------------------------------------------------- accounts
@app.route("/api/register", methods=["POST"])
def api_register():
    d = request.get_json(force=True, silent=True) or {}
    ok, msg = auth.register(d.get("username"), d.get("password"))
    if ok:
        session["user"] = d.get("username", "").strip().lower()
    return jsonify({"ok": ok, "message": msg, "user": current_user()}), (200 if ok else 400)


@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.get_json(force=True, silent=True) or {}
    ok, msg = auth.authenticate(d.get("username"), d.get("password"))
    if ok:
        session["user"] = d.get("username", "").strip().lower()
    return jsonify({"ok": ok, "message": msg, "user": current_user()}), (200 if ok else 401)


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("user", None)
    return jsonify({"ok": True})


@app.route("/api/me")
def api_me():
    user = current_user()
    if not user:
        return jsonify({"user": None})
    profile = auth.get_profile(user)
    if not profile:
        session.pop("user", None)
        return jsonify({"user": None})
    return jsonify({"user": user, "profile": profile})


@app.route("/api/preferences", methods=["POST"])
def api_preferences():
    user = current_user()
    if not user:
        return jsonify({"error": "not signed in"}), 401
    d = request.get_json(force=True, silent=True) or {}
    profile = auth.update_preferences(
        user,
        allergens=d.get("allergens"),
        health_weight=d.get("health_weight"),
        show_health=d.get("show_health"),
        show_eco=d.get("show_eco"),
    )
    return jsonify({"ok": True, "profile": profile})


@app.route("/api/favorite", methods=["POST"])
def api_favorite():
    user = current_user()
    if not user:
        return jsonify({"error": "not signed in"}), 401
    d = request.get_json(force=True, silent=True) or {}
    favs = auth.toggle_favorite(user, int(d.get("product_id")))
    return jsonify({"ok": True, "favorites": favs})


@app.route("/api/favorites")
def api_favorites():
    user = current_user()
    if not user:
        return jsonify({"favorites": []})
    profile = auth.get_profile(user)
    favs = [REC.get(i) for i in profile["favorites"] if REC.get(i)]
    return jsonify({"favorites": favs})


if __name__ == "__main__":
    print("BiteRec running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
