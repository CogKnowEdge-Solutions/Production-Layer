"""Tests for the Streamlit frontend.

Uses Streamlit's AppTest harness against a real API server started in a
background thread on an ephemeral port, so the UI and its auth token share the
same JWT secret. Does NOT require the OpenRouter agent to be running.
"""

import os
import socket
import threading

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENV"] = "testing"
os.environ["JWT_SECRET"] = "test-secret-key-at-least-32-bytes-long!!"

import httpx
import pytest

pytest.importorskip("streamlit")
pytest.importorskip("uvicorn")

from streamlit.testing.v1 import AppTest

FRONTEND = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "app.py")


@pytest.fixture(scope="module")
def server():
    """Start the real CareMatch API on an ephemeral port in a background thread."""
    import uvicorn

    from app.db.database import init_db
    from app.main import create_app

    init_db(force=True)
    app = create_app()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                if httpx.get(f"{base_url}/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            import time

            time.sleep(0.05)
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.fixture()
def token(server):
    resp = httpx.post(
        f"{server}/api/v1/auth/token",
        json={"username": "admin", "password": "admin-password-change-me"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _run(server, token=None):
    os.environ["API_URL"] = server
    os.environ["AGENT_URL"] = f"{server}"  # unused by these tests; must resolve
    at = AppTest.from_file(FRONTEND, default_timeout=60)
    if token:
        at.session_state["token"] = token
        at.session_state["username"] = "admin"
    at.run()
    return at


def test_login_gate_blocks_without_token(server):
    at = _run(server, token=None)
    assert not at.exception
    assert any("Log in" in str(i.value) for i in at.info)


def test_logged_in_renders_all_tabs(server, token):
    at = _run(server, token=token)
    assert not at.exception, [e.message for e in at.exception]
    labels = [t.label for t in at.tabs]
    assert {"📋 Trials", "🧪 Evaluate", "✅ Review", "👥 Caregivers", "🕵️ Audit", "🤖 Agent"} <= set(
        labels
    )


def test_create_trial_via_form(server, token):
    at = _run(server, token=token)
    assert not at.exception
    at.text_input[0].set_value("UI Test Trial")
    at.text_area[0].set_value("Inclusion criteria:\n- Patient is at least 30 years old")
    at.button[0].click()
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("UI Test Trial" in s.value for s in at.success)
