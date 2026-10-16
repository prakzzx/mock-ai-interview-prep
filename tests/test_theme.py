"""Pale pink theme: readable text contrast and no external assets."""

import re

import pytest

import app

P = app.PALETTE


def luminance(hex_color):
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(foreground, background):
    lighter, darker = sorted(
        (luminance(foreground), luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


# (text color, background it is drawn on) pairs used by the CSS
TEXT_ON = [
    ("text", "background"),
    ("text", "surface"),
    ("text", "surface_deep"),
    ("text", "bubble_user"),
    ("text", "button"),
    ("text", "button_hover"),
    ("text", "white"),
    ("accent_dark", "background"),
    ("accent_dark", "white"),
]


@pytest.mark.parametrize("foreground, background", TEXT_ON)
def test_text_contrast_meets_wcag_aa(foreground, background):
    assert contrast(P[foreground], P[background]) >= 4.5


def test_the_pink_is_pale():
    """Every surface is light (high luminance) and soft (not a saturated hot pink)."""
    for key in (
        "background",
        "surface",
        "surface_deep",
        "bubble_user",
        "button",
        "button_hover",
    ):
        assert luminance(P[key]) > 0.55, key
    assert contrast(P["text"], P["background"]) > 10  # dark text on pale pink


def test_css_contains_the_required_components():
    css = app.build_custom_css()
    assert "linear-gradient" in css  # sidebar gradient
    assert '[data-testid="stSidebar"]' in css
    assert "border-radius: 999px" in css  # rounded buttons
    assert ":hover" in css  # button hover state
    assert "stChatMessage" in css and "stChatMessageAvatarUser" in css
    assert ".interview-progress" in css
    assert "stAudioInput" in css


def test_css_has_no_external_assets_or_leftover_template_fields():
    css = app.build_custom_css()
    assert not re.search(r"https?:|//|@import|url\(|@font-face", css)
    assert "{background}" not in css and "{text}" not in css
    assert css.count("{") == css.count("}")


def test_every_palette_color_is_a_valid_hex():
    for value in P.values():
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", value)


def test_css_is_injected_from_exactly_one_function():
    import inspect

    source = inspect.getsource(app)
    assert source.count("unsafe_allow_html=True") == 2  # CSS + the progress banner
    assert source.count("def inject_custom_css") == 1
