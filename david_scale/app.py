"""
AIPulse — Public Flask App.

Check the pulse on AI. Serves AI tool rankings at port 8083.
Part of FLIPT AI (flipt.ai).
Dark theme, server-rendered, CoinMarketCap-style tables.
"""

import logging
import math
import os
from pathlib import Path

from flask import Flask, render_template, abort, request, redirect, url_for, flash

from david_scale.models import DavidScaleDB, CATEGORIES

logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET", "david-scale-dev")


def get_db() -> DavidScaleDB:
    """Get database instance."""
    return DavidScaleDB()


def _pseudo_score(tool: dict, rank: int) -> dict:
    """Create a display score from tool data before first real scoring run."""
    bench = tool.get("benchmark_score", 5.0) or 5.0
    usability = tool.get("usability_score", 5.0) or 5.0
    price = tool.get("price_monthly")

    # Compute value from benchmark + price
    if price is None:
        value = 5.0
    elif price == 0:
        value = min(10, bench + 1)
    else:
        raw = bench / math.log2(price + 2)
        value = round(max(0, min(10, raw * 4)), 2)

    # Pre-scoring: weight benchmark + usability + value equally
    david_score = round(bench * 0.4 + usability * 0.3 + value * 0.3, 2)

    return {
        "name": tool["name"],
        "slug": tool["slug"],
        "description": tool.get("description", ""),
        "website": tool.get("website", ""),
        "industry": bench,
        "influencer": None,  # N/A until scored
        "customer": None,    # N/A until scored
        "usability": usability,
        "value": value,
        "momentum": None,    # N/A until scored
        "david_score": david_score,
        "rank_in_category": rank,
        "mentions_count": 0,
        "price_monthly": price,
        "price_notes": tool.get("price_notes", ""),
        "learning_hours": tool.get("learning_hours"),
    }


@app.route("/")
def index():
    """Landing page — hero + top 3 per category."""
    db = get_db()
    categories = db.get_categories_with_counts()

    category_rankings = []
    has_scores = False

    for cat in categories:
        scores = db.get_latest_scores(category=cat["slug"])
        if scores:
            has_scores = True
            # Enrich with defaults for template
            for s in scores:
                s.setdefault("description", "")
                s.setdefault("website", "")
                s.setdefault("influencer", 5.0)
                s.setdefault("customer", s.get("sentiment", 5.0))
                s.setdefault("industry", s.get("benchmark", 5.0))
                s.setdefault("usability", 5.0)
                s.setdefault("value", 5.0)
                s.setdefault("price_monthly", None)
                s.setdefault("price_notes", "")
                s.setdefault("learning_hours", None)
            category_rankings.append({
                "name": cat["name"],
                "slug": cat["slug"],
                "tools": scores[:3],
            })
        else:
            tools = db.get_tools(category=cat["slug"])
            if tools:
                pseudo = [_pseudo_score(t, i+1) for i, t in enumerate(
                    sorted(tools, key=lambda t: t.get("benchmark_score", 0), reverse=True)
                )]
                category_rankings.append({
                    "name": cat["name"],
                    "slug": cat["slug"],
                    "tools": pseudo[:3],
                })

    return render_template(
        "index.html",
        categories=categories,
        category_rankings=category_rankings,
        rankings=has_scores,
        active_category=None,
    )


@app.route("/category/<slug>")
def category(slug):
    """Full rankings for a category."""
    if slug not in CATEGORIES:
        abort(404)

    db = get_db()
    categories = db.get_categories_with_counts()
    category_name = CATEGORIES[slug]

    scores = db.get_latest_scores(category=slug)
    if not scores:
        tools_raw = db.get_tools(category=slug)
        scores = [_pseudo_score(t, i+1) for i, t in enumerate(
            sorted(tools_raw, key=lambda t: t.get("benchmark_score", 0), reverse=True)
        )]

    # Enrich existing scores
    for s in scores:
        s.setdefault("influencer", 5.0)
        s.setdefault("customer", s.get("sentiment", 5.0))
        s.setdefault("industry", s.get("benchmark", 5.0))
        s.setdefault("usability", 5.0)
        s.setdefault("value", 5.0)
        s.setdefault("price_monthly", None)
        s.setdefault("price_notes", "")
        s.setdefault("learning_hours", None)

    return render_template(
        "category.html",
        categories=categories,
        category_name=category_name,
        tools=scores,
        active_category=slug,
    )


@app.route("/tool/<slug>")
def tool_detail(slug):
    """Individual tool score breakdown — gated for post-MVP."""
    db = get_db()
    categories = db.get_categories_with_counts()
    tool = db.get_tool_by_slug(slug)

    if not tool:
        abort(404)

    return render_template(
        "category.html",
        categories=categories,
        category_name=f"{tool['name']} — Coming Soon",
        tools=[],
        active_category=tool["category"],
    )


@app.route("/list-your-tool", methods=["GET", "POST"])
def list_your_tool():
    """CoinMarketCap-style listing application page."""
    db = get_db()
    categories = db.get_categories_with_counts()

    if request.method == "POST":
        tool_name = request.form.get("tool_name", "").strip()
        website = request.form.get("website", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        contact_email = request.form.get("contact_email", "").strip()
        contact_name = request.form.get("contact_name", "").strip()
        price_info = request.form.get("price_info", "").strip()
        why_list = request.form.get("why_list", "").strip()

        # Basic validation
        if not all([tool_name, website, category, contact_email]):
            flash("Please fill in all required fields.", "error")
            return render_template(
                "list_tool.html",
                categories=categories,
                all_categories=CATEGORIES,
                active_category=None,
            )

        db.save_listing_application(
            tool_name=tool_name,
            website=website,
            category=category,
            description=description,
            contact_email=contact_email,
            contact_name=contact_name,
            price_info=price_info,
            why_list=why_list,
        )

        return render_template(
            "list_tool_success.html",
            categories=categories,
            tool_name=tool_name,
            active_category=None,
        )

    return render_template(
        "list_tool.html",
        categories=categories,
        all_categories=CATEGORIES,
        active_category=None,
    )


def init_app():
    """Initialize the database and seed data."""
    db = DavidScaleDB()
    db.seed()
    logger.info("David Scale database initialized")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_app()
    print("Starting The David Scale at http://localhost:8083")
    app.run(host="0.0.0.0", port=8083, debug=True)
