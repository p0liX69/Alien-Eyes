import pytest

from alien_eyes.gaze import GazeTracker

FRAME_W, FRAME_H = 320, 240


def test_fallback_scan_stays_within_bounds():
    tracker = GazeTracker()
    now = 0.0
    for _ in range(40):
        gx, gy = tracker.update_from_faces([], FRAME_W, FRAME_H, now)
        assert -1.0 <= gx <= 1.0
        assert -1.0 <= gy <= 1.0
        now += 0.5


def test_damping_moves_toward_goal_gradually():
    tracker = GazeTracker()
    face = (200, 80, 80, 80)  # center (240,120) in a 320x240 frame -> goal (-0.5, 0.0)

    gx, gy = tracker.update_from_faces([face], FRAME_W, FRAME_H, 0.0)
    assert gx == pytest.approx(-0.04, abs=0.001)  # one damping step, not a snap to -0.5

    now = 1.0
    for _ in range(59):
        gx, gy = tracker.update_from_faces([face], FRAME_W, FRAME_H, now)
        now += 1.0

    assert gx == pytest.approx(-0.5, abs=0.02)  # converges after enough frames
    assert gy == pytest.approx(0.0, abs=0.02)
