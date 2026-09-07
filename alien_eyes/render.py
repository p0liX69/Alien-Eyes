# alien_eyes/render.py
from PIL import Image, ImageDraw

from alien_eyes import config


def draw_eye(gx, gy, blink_amount=0.0):
    img = Image.new("RGB", (config.PANEL_SIZE, config.PANEL_SIZE), config.SCLERA_COLOR)
    draw = ImageDraw.Draw(img)

    center = config.PANEL_SIZE / 2
    cx = center + gx * config.MAX_OFFSET
    cy = center + gy * config.MAX_OFFSET

    draw.ellipse(
        [cx - config.IRIS_RADIUS, cy - config.IRIS_RADIUS, cx + config.IRIS_RADIUS, cy + config.IRIS_RADIUS],
        fill=config.IRIS_COLOR,
    )
    draw.ellipse(
        [cx - config.PUPIL_RADIUS, cy - config.PUPIL_RADIUS, cx + config.PUPIL_RADIUS, cy + config.PUPIL_RADIUS],
        fill=config.PUPIL_COLOR,
    )

    if blink_amount > 0.0:
        blink_layer = Image.new("RGB", img.size, config.SCLERA_COLOR)
        img = Image.blend(img, blink_layer, min(blink_amount, 1.0))

    return img
