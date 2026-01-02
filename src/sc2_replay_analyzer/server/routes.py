"""Flask route definitions."""
from flask import jsonify, render_template

from .api import get_mmr_history


def register_routes(app):
    """Register all routes on the Flask app."""

    @app.route("/api/v1/mmr/history")
    def mmr_history():
        """Get MMR history for graphing."""
        result = get_mmr_history(limit=100)
        return jsonify(result)

    @app.route("/overlays/mmr-graph")
    def mmr_graph_overlay():
        """Render MMR graph overlay page."""
        return render_template("mmr_graph.html")
