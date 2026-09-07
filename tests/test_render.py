# tests/test_render.py
from alien_eyes import config, render


def test_draw_eye_returns_correct_size_and_mode():
    img = render.draw_eye(0.0, 0.0)
    assert img.size == (config.PANEL_SIZE, config.PANEL_SIZE)
    assert img.mode == "RGB"


def test_draw_eye_centers_pupil_when_looking_straight_ahead():
    img = render.draw_eye(0.0, 0.0)
    center = config.PANEL_SIZE // 2
    assert img.getpixel((center, center)) == config.PUPIL_COLOR


def test_draw_eye_full_blink_is_uniformly_sclera_colored():
    img = render.draw_eye(0.5, -0.3, blink_amount=1.0)
    colors = img.getcolors(maxcolors=1)
    assert colors is not None
    _, color = colors[0]
    assert color == config.SCLERA_COLOR
