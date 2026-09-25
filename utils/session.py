"""Authenticated-session reuse.

Logs in once, using the SAME `browser` object pytest-playwright already
launches for the test session (never a second, separately-managed
Playwright instance - nesting `sync_playwright()` inside pytest-playwright's
own event loop raises "Sync API inside the asyncio loop"), and caches the
resulting storage_state (cookies + localStorage) to disk under
.auth/state.json. The root conftest.py's `page` fixture then loads every
feature/module test's context from that cached state, so a full module run
performs the real login UI flow once instead of once per test case. If the
cached state has gone stale (expired session), it's regenerated
automatically.

tests/login/ deliberately opts out of this (see its own conftest.py) since
those tests exercise the login page/flow itself and must start from a
genuinely unauthenticated context.
"""
from pathlib import Path

from config.settings import BASE_URL, LOGIN_EMAIL, LOGIN_PASSWORD, PROJECT_ROOT

AUTH_DIR = PROJECT_ROOT / ".auth"
AUTH_STATE_PATH = AUTH_DIR / "state.json"

# Login redirects to /wta/Information (see pages/login_page.py, tests/login).
# Reused here as a stable "am I actually logged in" probe URL.
AUTHENTICATED_HOME = BASE_URL.split("/auth/")[0] + "/wta/Information"


def _state_is_valid(browser) -> bool:
    if not AUTH_STATE_PATH.exists():
        return False
    context = None
    try:
        context = browser.new_context(storage_state=str(AUTH_STATE_PATH))
        page = context.new_page()
        page.goto(AUTHENTICATED_HOME, wait_until="networkidle", timeout=20000)
        return "/auth/login" not in page.url
    except Exception:
        return False
    finally:
        if context is not None:
            context.close()


def _login_and_cache(browser) -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        page.locator("#email").fill(LOGIN_EMAIL)
        page.locator("#password").fill(LOGIN_PASSWORD)
        page.locator('button[type="submit"]').click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        if "/auth/login" in page.url:
            raise RuntimeError(
                "Session-cache login failed: still on /auth/login after "
                "submitting valid credentials. Check .env / the live app."
            )
        context.storage_state(path=str(AUTH_STATE_PATH))
    finally:
        context.close()


def ensure_session_cached(browser) -> Path:
    """Returns a path to a valid storage_state file, logging in once (and
    only once) if no still-valid cached session exists. `browser` must be
    pytest-playwright's own session-scoped Browser fixture - see
    conftest.py::_auth_state_path."""
    if not _state_is_valid(browser):
        _login_and_cache(browser)
    return AUTH_STATE_PATH
