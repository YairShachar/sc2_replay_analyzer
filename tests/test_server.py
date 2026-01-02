"""Tests for HTTP server module."""
import pytest

# Check if Flask is available
try:
    from flask import Flask
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not FLASK_AVAILABLE,
    reason="Flask not installed - skip server tests"
)


@pytest.fixture
def app(mock_db_path, db_with_replays):
    """Create Flask test app with test database."""
    from sc2_replay_analyzer.server import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


class TestServerModule:
    """Tests for server module functions."""

    def test_is_flask_available(self):
        """is_flask_available returns True when Flask is installed."""
        from sc2_replay_analyzer.server import is_flask_available

        assert is_flask_available() is True

    def test_create_app_returns_flask_app(self, mock_db_path):
        """create_app returns a Flask application."""
        from sc2_replay_analyzer.server import create_app

        app = create_app()
        assert isinstance(app, Flask)

    def test_find_available_port(self):
        """find_available_port returns a valid port."""
        from sc2_replay_analyzer.server import find_available_port

        port = find_available_port(start_port=9000)
        assert isinstance(port, int)
        assert 9000 <= port < 9010


class TestApiEndpoints:
    """Tests for API endpoints."""

    def test_mmr_history_returns_json(self, client):
        """GET /api/v1/mmr/history returns JSON data."""
        response = client.get("/api/v1/mmr/history")

        assert response.status_code == 200
        data = response.get_json()
        assert "data" in data
        assert "player_name" in data
        assert isinstance(data["data"], list)

    def test_mmr_history_contains_expected_fields(self, client):
        """MMR history entries contain date, mmr, result, matchup."""
        response = client.get("/api/v1/mmr/history")
        data = response.get_json()

        # We have replays in db_with_replays fixture
        if data["data"]:
            entry = data["data"][0]
            assert "date" in entry
            assert "mmr" in entry
            assert "result" in entry
            assert "matchup" in entry


class TestOverlayEndpoints:
    """Tests for overlay page endpoints."""

    def test_mmr_graph_overlay_returns_html(self, client):
        """GET /overlays/mmr-graph returns HTML page."""
        response = client.get("/overlays/mmr-graph")

        assert response.status_code == 200
        assert b"mmrChart" in response.data
        assert b"Chart.js" in response.data or b"chart.js" in response.data

    def test_static_css_accessible(self, client):
        """Static CSS file is accessible."""
        response = client.get("/static/css/overlay.css")

        assert response.status_code == 200
        assert b"transparent" in response.data

    def test_static_js_accessible(self, client):
        """Static JS file is accessible."""
        response = client.get("/static/js/mmr_graph.js")

        assert response.status_code == 200
        assert b"fetchData" in response.data


class TestApiModule:
    """Tests for api.py data transformation."""

    def test_get_mmr_history_returns_dict_with_data(self, mock_db_path, db_with_replays):
        """get_mmr_history returns a dict with player_name and data."""
        from sc2_replay_analyzer.server.api import get_mmr_history

        result = get_mmr_history(limit=100)
        assert isinstance(result, dict)
        assert "player_name" in result
        assert "data" in result
        assert isinstance(result["data"], list)

    def test_get_mmr_history_filters_no_mmr(self, mock_db_path, initialized_db):
        """get_mmr_history filters out entries without MMR."""
        from sc2_replay_analyzer import db
        from sc2_replay_analyzer.server.api import get_mmr_history

        # Insert replay without MMR
        db.insert_replay({
            "replay_id": "no_mmr_123",
            "file_path": "/test/replay.SC2Replay",
            "played_at": "2024-12-15T12:00:00+00:00",
            "map_name": "Test Map",
            "matchup": "TvZ",
            "result": "Win",
            "player_mmr": None,  # No MMR
        })

        result = get_mmr_history(limit=100)
        # Should not include the replay without MMR
        for entry in result["data"]:
            assert entry["mmr"] is not None

    def test_get_mmr_history_ordered_oldest_first(self, mock_db_path, db_with_replays):
        """get_mmr_history returns data oldest first for graphing."""
        from sc2_replay_analyzer.server.api import get_mmr_history

        result = get_mmr_history(limit=100)
        data = result["data"]
        if len(data) >= 2:
            # First entry should be older than last entry
            assert data[0]["date"] <= data[-1]["date"]
