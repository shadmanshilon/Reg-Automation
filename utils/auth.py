"""Shared per-test authentication helper.

Every feature/module test's `page` fixture already starts from a cached,
authenticated context (see utils/session.py + conftest.py::page) - so in
the normal case this just confirms that and logs the step, without
repeating the login UI flow. If the cached session has somehow gone stale
mid-run, it falls back to a real login so the test still passes rather than
failing on a session it can silently recover from.
"""
from config.settings import LOGIN_EMAIL, LOGIN_PASSWORD
from pages.login_page import LoginPage
from pages.landing_page import LandingPage
from utils.session import AUTHENTICATED_HOME


def perform_login(case, page, dismiss_cookies: bool = True):
    """dismiss_cookies=False for tests (e.g. LANDING_04) that specifically
    need to observe/interact with the still-undismissed cookie banner
    themselves."""
    case.step(1, "Ensure an authenticated session (reused across this module's test cases)")
    case.action("Navigating to the workspace", kind="navigate")
    page.goto(AUTHENTICATED_HOME, wait_until="networkidle")

    if "/auth/login" in page.url:
        case.action("Cached session was invalid/expired - logging in", kind="navigate")
        login_page = LoginPage(page)
        login_page.goto()
        case.fill(login_page.email, LOGIN_EMAIL, "Email field")
        case.fill(login_page.password, LOGIN_PASSWORD, "Password field", mask=True)
        case.click(login_page.submit, "Log In button")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
    else:
        case.action("Reusing the existing authenticated session", kind="verify")

    if dismiss_cookies:
        LandingPage(page).accept_cookies_if_present()
