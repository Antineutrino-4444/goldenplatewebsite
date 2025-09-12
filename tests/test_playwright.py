import pytest

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    pytest.skip('playwright not installed', allow_module_level=True)


def test_basic_playwright():
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            pytest.skip('chromium not available')
        page = browser.new_page()
        page.goto('about:blank')
        assert page.title() == ''
        browser.close()
