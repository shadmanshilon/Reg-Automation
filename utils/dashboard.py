"""Live execution dashboard: a small local HTTP server that serves
dashboard/dashboard.html plus a live_state.json file the page polls, so the
whole run's progress - current step, current action, current assertion -
can be watched in real time in a browser tab alongside the headed test
browser."""
import json
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from config.settings import REPORTS_DIR, PROJECT_ROOT

STATE_PATH = REPORTS_DIR / "live_state.json"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"

_lock = threading.Lock()
_server = None
_state = {
    "session": {
        "status": "idle", "total": 0, "completed": 0,
        "passed": 0, "failed": 0, "blocked": 0,
        "started_at": None, "app_url": "", "account": "",
    },
    "current": {
        "feature": "", "case_id": "", "title": "", "steps": [],
        "action": None, "assertion": None,
    },
    "log": [],
}


def _write():
    """Atomic-replace, with retries: on Windows, os.replace can transiently
    fail with PermissionError if the HTTP server thread has the target file
    open for a GET at that exact instant, or if the project folder sits
    under OneDrive/antivirus scanning that holds a longer-than-expected
    lock. This is a visualization write only - it must never fail an
    actual test, so after exhausting retries it gives up silently rather
    than raising."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(_state), encoding="utf-8")
    for attempt in range(25):
        try:
            tmp.replace(STATE_PATH)
            return
        except PermissionError:
            time.sleep(min(0.05 * (attempt + 1), 0.5))
    try:
        tmp.replace(STATE_PATH)
    except PermissionError:
        pass


def _log(kind: str, text: str):
    _state["log"].append({"t": time.strftime("%H:%M:%S"), "kind": kind, "text": text})
    _state["log"] = _state["log"][-200:]


def init_session(total_tests: int, app_url: str, account: str):
    with _lock:
        _state["session"].update({
            "status": "running", "total": total_tests, "completed": 0,
            "passed": 0, "failed": 0, "blocked": 0,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "app_url": app_url, "account": account,
        })
        _state["current"] = {"feature": "", "case_id": "", "title": "", "steps": [], "action": None, "assertion": None}
        _state["log"] = []
        _log("session", f"Starting {total_tests} test case(s).")
        _write()


def start_case(feature: str, case_id: str, title: str):
    with _lock:
        _state["current"] = {
            "feature": feature, "case_id": case_id, "title": title,
            "steps": [], "action": None, "assertion": None,
        }
        _log("case", f"{case_id} - {title}")
        _write()


def add_step(n: int, text: str):
    with _lock:
        for s in _state["current"]["steps"]:
            if s["status"] == "running":
                s["status"] = "done"
        _state["current"]["steps"].append({"n": n, "text": text, "status": "running"})
        _log("step", f"Step {n}: {text}")
        _write()


def set_action(kind: str, text: str):
    with _lock:
        _state["current"]["action"] = {"kind": kind, "text": text}
        _log("action", text)
        _write()


def set_assertion(text: str, passed):
    with _lock:
        _state["current"]["assertion"] = {"text": text, "passed": passed}
        _log("assert", f"{'PASS' if passed else 'FAIL'} - {text}")
        _write()


def finish_case(result: str):
    with _lock:
        for s in _state["current"]["steps"]:
            if s["status"] == "running":
                s["status"] = "done"
        _state["session"]["completed"] += 1
        if result == "PASS":
            _state["session"]["passed"] += 1
        elif result == "FAIL":
            _state["session"]["failed"] += 1
        else:
            _state["session"]["blocked"] += 1
        _log("result", f"{_state['current']['case_id']} -> {result}")
        _write()


def finish_session():
    with _lock:
        _state["session"]["status"] = "done"
        _log("session", "Execution completed.")
        _write()


class _Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DASHBOARD_DIR), **kw)

    def translate_path(self, path):
        if path.split("?")[0].rstrip("/") == "/live_state.json":
            return str(STATE_PATH)
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass


def start_server(port: int = 8787):
    global _server
    for attempt_port in range(port, port + 15):
        try:
            _server = ThreadingHTTPServer(("127.0.0.1", attempt_port), _Handler)
            threading.Thread(target=_server.serve_forever, daemon=True).start()
            return attempt_port
        except OSError:
            continue
    return None


def open_browser(port: int):
    try:
        webbrowser.open(f"http://127.0.0.1:{port}/dashboard.html")
    except Exception:
        pass
