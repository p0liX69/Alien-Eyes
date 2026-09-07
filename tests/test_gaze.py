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


FACE_LEFT = (40, 80, 80, 80)    # center (80,120) -> goal (0.5, 0.0)
FACE_RIGHT = (240, 80, 80, 80)  # center (280,120) -> goal (-0.75, 0.0)


def test_lock_on_ignores_single_frame_blip():
    tracker = GazeTracker()

    now = 0.0
    gx = gy = 0.0
    for _ in range(60):
        gx, gy = tracker.update_from_faces([FACE_LEFT], FRAME_W, FRAME_H, now)
        now += 1.0

    assert gx == pytest.approx(0.5, abs=0.02)

    # a single frame of a second face shouldn't pull the lock away
    tracker.update_from_faces([FACE_RIGHT], FRAME_W, FRAME_H, now)
    now += 0.1
    gx, gy = tracker.update_from_faces([FACE_LEFT], FRAME_W, FRAME_H, now)

    assert gx > 0.3


def test_lock_on_switches_after_sustained_presence():
    tracker = GazeTracker()

    now = 0.0
    tracker.update_from_faces([FACE_LEFT], FRAME_W, FRAME_H, now)

    now = 1.0
    tracker.update_from_faces([FACE_RIGHT], FRAME_W, FRAME_H, now)  # candidate starts here

    now = 2.0  # 1s later, past the 400ms lock-on delay
    gx, gy = tracker.update_from_faces([FACE_RIGHT], FRAME_W, FRAME_H, now)

    for _ in range(58):
        now += 1.0
        gx, gy = tracker.update_from_faces([FACE_RIGHT], FRAME_W, FRAME_H, now)

    assert gx == pytest.approx(-0.75, abs=0.02)


def test_lock_survives_single_frame_detector_dropouts():
    # Real detectors (Haar cascade) flicker frame-to-frame even on a stationary face.
    # A single missed-detection frame must not yank the gaze toward the idle scan.
    tracker = GazeTracker()
    dt = 1.0 / 15.0  # realistic frame spacing

    now = 0.0
    gx = 0.0
    gx_prev = 0.0
    saw_backward_step = False
    for i in range(60):  # 4 seconds at 15fps
        faces = [FACE_LEFT] if i % 2 == 0 else []  # detector flickers every other frame
        gx, gy = tracker.update_from_faces(faces, FRAME_W, FRAME_H, now)
        if gx < gx_prev - 1e-9:
            saw_backward_step = True
        gx_prev = gx
        now += dt

    assert not saw_backward_step
    assert gx == pytest.approx(0.5, abs=0.02)
