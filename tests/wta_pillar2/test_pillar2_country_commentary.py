"""Pillar 2 > Country Commentary (/wta/CountryCommentary).

Manually verified against the live application first (scripts/discover_wta.py):
  - Left panel: jurisdiction list only (no categories).
  - Selecting a jurisdiction alone renders 'Commentary on <Country>, last
    updated <date>' plus an 'Export:' control and lettered/sectioned rich
    text (confirmed section: 'A. Legislative Framework')."""
import pytest

from pages.pillar2_country_commentary_page import CountryCommentaryPage
from pages.wta_common import wait_for_content
from utils.auth import perform_login
from utils.case import Case

FEATURE = "WTA Pillar2 CountryCommentary"


def _login_and_open(case, page):
    perform_login(case, page)
    cc = CountryCommentaryPage(page)
    case.action("Navigating to /wta/CountryCommentary", kind="navigate")
    cc.goto()
    return cc


@pytest.mark.smoke
def test_p2cc_01_page_loads_with_placeholder(page, result):
    case = Case(
        page, "P2CC_01", FEATURE, "Country Commentary loads with the jurisdiction placeholder",
        description="The page must load showing the left-panel instruction text.",
        precondition="User is logged in.",
        test_data="-",
        steps="1. Log in and open Pillar 2 > Country Commentary\n2. Verify the placeholder text is visible",
    )
    cc = _login_and_open(case, page)
    case.step(2, "Verify the placeholder is visible")
    ok = case.verify_visible(cc.placeholder_text, "left-panel instruction text")
    case.check("Placeholder instruction text is visible", ok, expected="visible", actual=ok,
               locator=cc.placeholder_text)

    actual = ("Country Commentary loaded with the placeholder visible." if ok else
              "Country Commentary did not show the expected placeholder.")
    result(case, actual, ok)
    assert ok, actual


@pytest.mark.smoke
def test_p2cc_02_selecting_jurisdiction_renders_commentary(page, result):
    case = Case(
        page, "P2CC_02", FEATURE, "Selecting a jurisdiction renders its commentary",
        description="Checking 'Australia' must render 'Commentary on Australia, last updated ...' with an "
                     "'Export:' control and an 'A. Legislative Framework' section.",
        precondition="User is logged in and on Country Commentary.",
        test_data="Country: Australia",
        steps="1. Log in and open Country Commentary\n2. Check 'Australia'\n"
              "3. Verify the commentary heading, Export control and first section are visible",
    )
    cc = _login_and_open(case, page)
    case.step(2, "Select Australia")
    case.click(cc.jurisdiction.country_checkbox("Australia"), "'Australia' checkbox")
    wait_for_content(cc.commentary_on_text)

    case.step(3, "Verify commentary content rendered")
    commentary_ok = case.verify_visible(cc.commentary_on_text, "'Commentary on ...' heading")
    export_ok = case.verify_visible(cc.export_label, "'Export:' control")
    section_ok = case.verify_visible(cc.legislative_framework_heading, "'A. Legislative Framework' section")
    ok = commentary_ok and export_ok and section_ok
    case.check("Commentary heading, Export control and first section are visible", ok,
               expected="all visible",
               actual=f"commentary={commentary_ok}, export={export_ok}, section={section_ok}")

    actual = ("Selecting Australia rendered its country commentary with the Export control and the "
              "'A. Legislative Framework' section." if ok else
              "Selecting a jurisdiction did not render the expected commentary content.")
    result(case, actual, ok)
    assert ok, actual


@pytest.mark.regression
def test_p2cc_03_country_search_no_match_message(page, result):
    case = Case(
        page, "P2CC_03", FEATURE, "Country search shows a 'no match' message for a bogus name",
        description="Searching for a non-existent country name must show 'No countries found matching...'.",
        precondition="User is logged in and on Country Commentary.",
        test_data="Search term: zzzznotarealcountry",
        steps="1. Log in and open Country Commentary\n2. Search for 'zzzznotarealcountry'\n"
              "3. Verify the 'No countries found' message is shown",
    )
    cc = _login_and_open(case, page)
    case.step(2, "Search for a bogus country name")
    case.fill(cc.jurisdiction.search_countries, "zzzznotarealcountry", "Search countries box")
    page.wait_for_timeout(500)

    case.step(3, "Verify the no-match message")
    ok = case.verify_visible(cc.jurisdiction.no_countries_message, "'No countries found' message")
    case.check("'No countries found' message is shown for a non-existent search term", ok,
               expected="visible", actual=ok, locator=cc.jurisdiction.no_countries_message)

    actual = ("Searching for a bogus country name correctly showed the 'No countries found' message." if ok
              else "The country search did not show the expected 'no match' message.")
    result(case, actual, ok)
    assert ok, actual
