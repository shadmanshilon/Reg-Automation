"""Draws a red outline around the element currently being interacted with
or verified, so a human watching the headed browser can follow along."""

_HL_ATTR = "data-qa-hl"

_CLEAR_JS = f"""() => {{
    document.querySelectorAll('[{_HL_ATTR}]').forEach(el => {{
        el.style.outline = '';
        el.style.boxShadow = '';
        el.removeAttribute('{_HL_ATTR}');
    }});
}}"""

_MARK_JS = f"""el => {{
    el.setAttribute('{_HL_ATTR}', '1');
    el.style.outline = '3px solid #ff2d2d';
    el.style.outlineOffset = '2px';
    el.style.boxShadow = '0 0 0 6px rgba(255,45,45,0.28)';
    el.scrollIntoView({{block: 'center', inline: 'center'}});
}}"""


def highlight(page, locator, hold_ms: int = 350):
    """Clears any previous highlight, outlines `locator` in red, and pauses
    briefly so it's visible before the action fires."""
    try:
        page.evaluate(_CLEAR_JS)
        locator.first.evaluate(_MARK_JS)
        page.wait_for_timeout(hold_ms)
    except Exception:
        pass


def clear(page):
    try:
        page.evaluate(_CLEAR_JS)
    except Exception:
        pass
