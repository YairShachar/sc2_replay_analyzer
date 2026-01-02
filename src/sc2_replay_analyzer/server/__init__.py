"""HTTP server for streaming overlays."""
import os
import socket
import threading

# Track if Flask is available
FLASK_AVAILABLE = False
try:
    from flask import Flask
    FLASK_AVAILABLE = True
except ImportError:
    pass


def is_flask_available() -> bool:
    """Check if Flask is installed."""
    return FLASK_AVAILABLE


def create_app():
    """Create Flask app with routes."""
    if not FLASK_AVAILABLE:
        raise ImportError(
            "Flask not installed. Install with: pip install sc2-replay-analyzer[server]"
        )

    # Use package-relative path for static files
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    app = Flask(
        __name__,
        static_folder=static_dir,
        template_folder=os.path.join(static_dir, "templates"),
    )

    from .routes import register_routes

    register_routes(app)
    return app


def find_available_port(start_port: int = 8080, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"No available ports in range {start_port}-{start_port + max_attempts}"
    )


def start_server_background(port: int = None):
    """Start server in background daemon thread with proper lifecycle.

    Returns:
        tuple: (port, server) or (None, None) if Flask not available
    """
    if not FLASK_AVAILABLE:
        return None, None

    from werkzeug.serving import make_server

    if port is None:
        port = find_available_port()

    app = create_app()
    server = make_server("127.0.0.1", port, app, threaded=True)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return port, server
