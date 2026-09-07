# Alien Gaze Rig Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python gaze-tracking codebase for the Alien Gaze Rig that runs today on a Mac (webcam in, on-screen window out) and runs unchanged in logic on a Raspberry Pi once the GC9A01 panels and camera are wired (Pi camera in, two SPI panels out).

**Architecture:** A hardware-agnostic core (`gaze.py` face-tracking/smoothing, `render.py` eye drawing) is wired to one of two swappable capture/output backend pairs (`capture.py` + `outputs/window_output.py` for Mac sim, `capture.py` + `outputs/spi_output.py` for Pi) by `main.py`, which auto-detects the platform or honors a `--sim`/`--pi` flag.

**Tech Stack:** Python 3, OpenCV (`opencv-python`) for capture + Haar-cascade face detection, Pillow for image drawing, `adafruit-circuitpython-gc9a01a` + Blinka for the Pi's SPI panels, `picamera2` for the Pi camera, `pytest` for tests.

## Global Constraints

- Damping constant is `0.08`, lock-on delay is `400`ms — exact values from the build sheet (`docs/build-sheet.md` §5–§6) and the approved spec.
- All tunable constants (damping, lock-on delay, switch threshold, colors, panel/circle sizes, detector params) live in `alien_eyes/config.py` — no magic numbers in other files.
- Hardware-init failures (camera won't open, SPI panel unresponsive) fail fast with a clear error at startup — no silent partial operation.
- A single bad frame read is skipped, not fatal — the loop keeps running.
- `capture.py`'s Pi path and everything in `outputs/` wrap hardware/OS calls directly and are **not** unit tested — per the spec's scoped testing exception, they're verified manually (Task 8). Everything else must have unit tests.
- Files stay small and single-purpose (typical 200–400 lines) per repo convention.

---

### Task 1: Project scaffolding

**Files:**
- Create: `alien_eyes/__init__.py`
- Create: `alien_eyes/outputs/__init__.py`
- Create: `requirements-common.txt`
- Create: `requirements-pi.txt`
- Create: `pyproject.toml`
- Create: `.gitignore`

**Interfaces:**
- Produces: an importable `alien_eyes` package (and `alien_eyes.outputs` subpackage) that later tasks add modules to; a working `pytest` command from the repo root.

- [ ] **Step 1: Create the package directories and empty `__init__.py` files**

```bash
mkdir -p alien_eyes/outputs tests
touch alien_eyes/__init__.py alien_eyes/outputs/__init__.py
```

- [ ] **Step 2: Create `requirements-common.txt`**

```
opencv-python>=4.9
pillow>=10.0
numpy>=1.26
pytest>=8.0
```

- [ ] **Step 3: Create `requirements-pi.txt`**

```
-r requirements-common.txt
adafruit-circuitpython-gc9a01a
adafruit-blinka
picamera2
```

- [ ] **Step 4: Create `pyproject.toml`** so tests can `import alien_eyes` without installing the package

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

- [ ] **Step 5: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 6: Create a virtualenv and install common requirements**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-common.txt
```

- [ ] **Step 7: Verify the environment works**

Run: `pytest`
Expected: `no tests ran` (exit code 5) — confirms pytest runs cleanly with no collection errors before any real code exists.

- [ ] **Step 8: Commit**

```bash
git add alien_eyes/__init__.py alien_eyes/outputs/__init__.py \
        requirements-common.txt requirements-pi.txt pyproject.toml .gitignore
git commit -m "chore: scaffold alien_eyes package and pytest config"
```

---

### Task 2: GazeTracker — damping and fallback scan

**Files:**
- Create: `alien_eyes/config.py`
- Create: `alien_eyes/gaze.py`
- Test: `tests/test_gaze.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (first real logic module).
- Produces: `GazeTracker(damping=..., lock_on_ms=..., switch_threshold=..., cascade_path=None)` with `update_from_faces(faces, frame_width, frame_height, now) -> (gx, gy)` and `update(gray_frame, now=None) -> (gx, gy)`. Later tasks (`main.py`) call `update()`; this task's tests call `update_from_faces()` directly to avoid needing real camera images.

- [ ] **Step 1: Write `alien_eyes/config.py`**

```python
# alien_eyes/config.py
DAMPING = 0.08
LOCK_ON_MS = 400
LOCK_SWITCH_THRESHOLD = 0.35

SCLERA_COLOR = (235, 235, 230)
IRIS_COLOR = (40, 120, 60)
PUPIL_COLOR = (10, 10, 10)

PANEL_SIZE = 240
IRIS_RADIUS = 55
PUPIL_RADIUS = 24
MAX_OFFSET = 34

CASCADE_MIN_SIZE = (60, 60)
DETECT_SCALE_FACTOR = 1.2
DETECT_MIN_NEIGHBORS = 5
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_gaze.py
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_gaze.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alien_eyes.gaze'`

- [ ] **Step 4: Write the minimal `alien_eyes/gaze.py`**

```python
# alien_eyes/gaze.py
import math
import time

import cv2

from alien_eyes import config


class GazeTracker:
    def __init__(
        self,
        damping=config.DAMPING,
        lock_on_ms=config.LOCK_ON_MS,
        switch_threshold=config.LOCK_SWITCH_THRESHOLD,
        cascade_path=None,
    ):
        self.damping = damping
        self.lock_on_ms = lock_on_ms
        self.switch_threshold = switch_threshold

        self.tx = 0.0
        self.ty = 0.0
        self._lock_goal = None

        path = cascade_path or (cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self._cascade = cv2.CascadeClassifier(path)

    def update(self, gray_frame, now=None):
        if now is None:
            now = time.time()
        height, width = gray_frame.shape[:2]
        faces = self._cascade.detectMultiScale(
            gray_frame,
            config.DETECT_SCALE_FACTOR,
            config.DETECT_MIN_NEIGHBORS,
            minSize=config.CASCADE_MIN_SIZE,
        )
        return self.update_from_faces(list(faces), width, height, now)

    def update_from_faces(self, faces, frame_width, frame_height, now):
        if faces:
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            nx = ((x + w / 2) / frame_width) * 2 - 1
            ny = ((y + h / 2) / frame_height) * 2 - 1
            goal = (-nx, ny)
            self._lock_goal = goal
            target = self._lock_goal
        else:
            self._lock_goal = None
            target = self._fallback_goal(now)

        self.tx += (target[0] - self.tx) * self.damping
        self.ty += (target[1] - self.ty) * self.damping
        return self.tx, self.ty

    def _fallback_goal(self, now):
        return (math.sin(now * 0.3) * 0.6, math.sin(now * 0.21) * 0.3)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_gaze.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add alien_eyes/config.py alien_eyes/gaze.py tests/test_gaze.py
git commit -m "feat: add GazeTracker damping and fallback scan"
```

---

### Task 3: GazeTracker — lock-on delay

**Files:**
- Modify: `alien_eyes/gaze.py`
- Test: `tests/test_gaze.py`

**Interfaces:**
- Consumes: `GazeTracker` from Task 2 — this task changes its internal `_lock_goal` handling but keeps `update_from_faces(faces, frame_width, frame_height, now) -> (gx, gy)`'s public signature and behavior identical for the single-face case (Task 2's tests must keep passing).
- Produces: the same `GazeTracker` now ignoring brief second-face blips and only switching targets after `lock_on_ms` of sustained presence — this is the version `main.py` (Task 7) will use.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gaze.py (append)

FACE_LEFT = (0, 80, 80, 80)     # center (40,120) -> goal (0.5, 0.0)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gaze.py -v`
Expected: FAIL on `test_lock_on_ignores_single_frame_blip` — the Task 2 implementation snaps `_lock_goal` to any new face immediately, so `gx` jumps toward `FACE_RIGHT`'s goal instead of staying near 0.5.

- [ ] **Step 3: Update `alien_eyes/gaze.py` to add lock-on delay**

```python
# alien_eyes/gaze.py
import math
import time

import cv2

from alien_eyes import config


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class GazeTracker:
    def __init__(
        self,
        damping=config.DAMPING,
        lock_on_ms=config.LOCK_ON_MS,
        switch_threshold=config.LOCK_SWITCH_THRESHOLD,
        cascade_path=None,
    ):
        self.damping = damping
        self.lock_on_ms = lock_on_ms
        self.switch_threshold = switch_threshold

        self.tx = 0.0
        self.ty = 0.0
        self._lock_goal = None
        self._pending_goal = None
        self._pending_since = None

        path = cascade_path or (cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self._cascade = cv2.CascadeClassifier(path)

    def update(self, gray_frame, now=None):
        if now is None:
            now = time.time()
        height, width = gray_frame.shape[:2]
        faces = self._cascade.detectMultiScale(
            gray_frame,
            config.DETECT_SCALE_FACTOR,
            config.DETECT_MIN_NEIGHBORS,
            minSize=config.CASCADE_MIN_SIZE,
        )
        return self.update_from_faces(list(faces), width, height, now)

    def update_from_faces(self, faces, frame_width, frame_height, now):
        if faces:
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            nx = ((x + w / 2) / frame_width) * 2 - 1
            ny = ((y + h / 2) / frame_height) * 2 - 1
            goal = (-nx, ny)
            self._track_lock(goal, now)
            target = self._lock_goal
        else:
            self._lock_goal = None
            self._pending_goal = None
            self._pending_since = None
            target = self._fallback_goal(now)

        self.tx += (target[0] - self.tx) * self.damping
        self.ty += (target[1] - self.ty) * self.damping
        return self.tx, self.ty

    def _track_lock(self, goal, now):
        if self._lock_goal is None:
            self._lock_goal = goal
            self._pending_goal = None
            self._pending_since = None
            return

        if _distance(goal, self._lock_goal) <= self.switch_threshold:
            self._lock_goal = goal
            self._pending_goal = None
            self._pending_since = None
            return

        if self._pending_goal is None or _distance(goal, self._pending_goal) > self.switch_threshold:
            self._pending_goal = goal
            self._pending_since = now
            return

        if now - self._pending_since >= self.lock_on_ms / 1000.0:
            self._lock_goal = goal
            self._pending_goal = None
            self._pending_since = None

    def _fallback_goal(self, now):
        return (math.sin(now * 0.3) * 0.6, math.sin(now * 0.21) * 0.3)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_gaze.py -v`
Expected: PASS (4 tests — the two from Task 2 still pass, plus the two new ones)

- [ ] **Step 5: Commit**

```bash
git add alien_eyes/gaze.py tests/test_gaze.py
git commit -m "feat: add lock-on delay so GazeTracker ignores brief second-face blips"
```

---

### Task 4: Eye rendering

**Files:**
- Create: `alien_eyes/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `alien_eyes.config` constants from Task 2.
- Produces: `draw_eye(gx, gy, blink_amount=0.0) -> PIL.Image.Image`, a 240×240 RGB image. `main.py` (Task 7) calls this with the `(gx, gy)` from `GazeTracker.update()`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alien_eyes.render'`

- [ ] **Step 3: Write `alien_eyes/render.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_render.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add alien_eyes/render.py tests/test_render.py
git commit -m "feat: render sclera/iris/pupil eye image with blink support"
```

---

### Task 5: Camera capture backends

**Files:**
- Create: `alien_eyes/capture.py`
- Test: `tests/test_capture.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `WebcamCapture(device_index=0)` and `PiCameraCapture()`, both exposing `.read() -> grayscale numpy array or None` and `.close()`. `main.py` (Task 7) instantiates one or the other based on backend.

- [ ] **Step 1: Write the failing tests** (only `WebcamCapture` is testable without real hardware — see Global Constraints)

```python
# tests/test_capture.py
from unittest.mock import MagicMock, patch

import pytest

from alien_eyes.capture import WebcamCapture


def test_webcam_capture_raises_when_device_unavailable():
    fake_cv2_capture = MagicMock()
    fake_cv2_capture.isOpened.return_value = False

    with patch("alien_eyes.capture.cv2.VideoCapture", return_value=fake_cv2_capture):
        with pytest.raises(RuntimeError, match="Could not open webcam"):
            WebcamCapture(device_index=3)


def test_webcam_capture_read_returns_none_on_failed_frame():
    fake_cv2_capture = MagicMock()
    fake_cv2_capture.isOpened.return_value = True
    fake_cv2_capture.read.return_value = (False, None)

    with patch("alien_eyes.capture.cv2.VideoCapture", return_value=fake_cv2_capture):
        cap = WebcamCapture()
        assert cap.read() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_capture.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alien_eyes.capture'`

- [ ] **Step 3: Write `alien_eyes/capture.py`**

```python
# alien_eyes/capture.py
import cv2


class WebcamCapture:
    def __init__(self, device_index=0):
        self._cap = cv2.VideoCapture(device_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open webcam at index {device_index}")

    def read(self):
        ok, frame = self._cap.read()
        if not ok:
            return None
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def close(self):
        self._cap.release()


class PiCameraCapture:
    def __init__(self):
        from picamera2 import Picamera2  # Pi-only import, kept out of module scope

        self._picam2 = Picamera2()
        preview_config = self._picam2.create_preview_configuration(
            main={"size": (320, 240), "format": "RGB888"}
        )
        self._picam2.configure(preview_config)
        self._picam2.start()

    def read(self):
        frame = self._picam2.capture_array()
        return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

    def close(self):
        self._picam2.stop()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_capture.py -v`
Expected: PASS (2 tests). `PiCameraCapture` has no automated test — it wraps `picamera2`, which only installs on the Pi; it's verified manually once hardware is wired (Task 8 covers the Mac side now, a follow-up pass covers the Pi side later).

- [ ] **Step 5: Commit**

```bash
git add alien_eyes/capture.py tests/test_capture.py
git commit -m "feat: add webcam and Pi camera capture backends"
```

---

### Task 6: Output backends

**Files:**
- Create: `alien_eyes/outputs/window_output.py`
- Create: `alien_eyes/outputs/spi_output.py`

**Interfaces:**
- Consumes: nothing from earlier tasks directly (takes a `PIL.Image.Image` at runtime, produced by `render.draw_eye` from Task 4).
- Produces: `WindowOutput()` and `SPIOutput()`, both exposing `.push(image)`, `.should_quit() -> bool`, and `.close()`. `main.py` (Task 7) calls these in its loop.

No automated tests for this task — both classes wrap hardware/OS calls directly (a real display window, real SPI hardware) per the Global Constraints scoped exception. They're verified manually: `WindowOutput` in Task 8's Mac walkthrough, `SPIOutput` once the Pi is wired.

- [ ] **Step 1: Write `alien_eyes/outputs/window_output.py`**

```python
# alien_eyes/outputs/window_output.py
import cv2
import numpy as np


class WindowOutput:
    def __init__(self, window_name="Alien Gaze Rig (sim)"):
        self._window_name = window_name
        self._quit_requested = False

    def push(self, image):
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        tiled = np.hstack([frame, frame])  # mimics the two physical panels side by side
        cv2.imshow(self._window_name, tiled)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            self._quit_requested = True

    def should_quit(self):
        return self._quit_requested

    def close(self):
        cv2.destroyWindow(self._window_name)
```

- [ ] **Step 2: Write `alien_eyes/outputs/spi_output.py`**

```python
# alien_eyes/outputs/spi_output.py
import board
import busio
import digitalio
from adafruit_gc9a01a import GC9A01A


class SPIOutput:
    def __init__(self):
        spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI)
        self._eye_r = GC9A01A(
            spi,
            cs=digitalio.DigitalInOut(board.CE0),
            dc=digitalio.DigitalInOut(board.D24),
            rst=digitalio.DigitalInOut(board.D25),
            baudrate=40_000_000,
        )
        self._eye_l = GC9A01A(
            spi,
            cs=digitalio.DigitalInOut(board.CE1),
            dc=digitalio.DigitalInOut(board.D23),
            rst=digitalio.DigitalInOut(board.D25),
            baudrate=40_000_000,
        )

    def push(self, image):
        self._eye_r.image(image)
        self._eye_l.image(image)

    def should_quit(self):
        return False

    def close(self):
        pass
```

- [ ] **Step 3: Verify the sim side imports cleanly** (the Pi side can't be exercised without hardware yet)

Run: `python -c "from alien_eyes.outputs.window_output import WindowOutput"`
Expected: no output, exit code 0 (import succeeds)

- [ ] **Step 4: Commit**

```bash
git add alien_eyes/outputs/window_output.py alien_eyes/outputs/spi_output.py
git commit -m "feat: add window and SPI output backends"
```

---

### Task 7: Main entrypoint and backend selection

**Files:**
- Create: `alien_eyes/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `GazeTracker` (Task 3), `render.draw_eye` (Task 4), `WebcamCapture`/`PiCameraCapture` (Task 5), `WindowOutput`/`SPIOutput` (Task 6).
- Produces: `pick_backend(sim_flag, is_pi_fn=is_raspberry_pi) -> "sim" | "pi"`, `parse_args(argv=None)`, `main(argv=None)` — the `python -m alien_eyes.main` entrypoint.

- [ ] **Step 1: Write the failing tests** (only the pure functions — `run()`/`build_capture()`/`build_output()` touch real hardware and are verified manually in Task 8)

```python
# tests/test_main.py
from alien_eyes.main import parse_args, pick_backend


def test_pick_backend_sim_flag_forces_sim():
    assert pick_backend(True, is_pi_fn=lambda: True) == "sim"


def test_pick_backend_pi_flag_forces_pi():
    assert pick_backend(False, is_pi_fn=lambda: False) == "pi"


def test_pick_backend_auto_detects_pi():
    assert pick_backend(None, is_pi_fn=lambda: True) == "pi"


def test_pick_backend_auto_detects_mac():
    assert pick_backend(None, is_pi_fn=lambda: False) == "sim"


def test_parse_args_sim_flag():
    args = parse_args(["--sim"])
    assert args.sim is True
    assert args.pi is False


def test_parse_args_pi_flag():
    args = parse_args(["--pi"])
    assert args.sim is False
    assert args.pi is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'alien_eyes.main'`

- [ ] **Step 3: Write `alien_eyes/main.py`**

```python
# alien_eyes/main.py
import argparse

from alien_eyes import render
from alien_eyes.gaze import GazeTracker


def is_raspberry_pi():
    try:
        with open("/proc/device-tree/model") as f:
            return "raspberry pi" in f.read().lower()
    except FileNotFoundError:
        return False


def pick_backend(sim_flag, is_pi_fn=is_raspberry_pi):
    if sim_flag is True:
        return "sim"
    if sim_flag is False:
        return "pi"
    return "pi" if is_pi_fn() else "sim"


def build_capture(backend):
    if backend == "pi":
        from alien_eyes.capture import PiCameraCapture

        return PiCameraCapture()
    from alien_eyes.capture import WebcamCapture

    return WebcamCapture()


def build_output(backend):
    if backend == "pi":
        from alien_eyes.outputs.spi_output import SPIOutput

        return SPIOutput()
    from alien_eyes.outputs.window_output import WindowOutput

    return WindowOutput()


def run(capture, output, tracker):
    while not output.should_quit():
        frame = capture.read()
        if frame is None:
            continue
        gx, gy = tracker.update(frame)
        img = render.draw_eye(gx, gy)
        output.push(img)
    capture.close()
    output.close()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Alien Gaze Rig")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sim", action="store_true", help="Force Mac simulation mode")
    group.add_argument("--pi", action="store_true", help="Force Pi hardware mode")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    sim_flag = True if args.sim else (False if args.pi else None)
    backend = pick_backend(sim_flag)
    capture = build_capture(backend)
    output = build_output(backend)
    tracker = GazeTracker()
    run(capture, output, tracker)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: PASS (all tests across `test_gaze.py`, `test_render.py`, `test_capture.py`, `test_main.py`)

- [ ] **Step 6: Commit**

```bash
git add alien_eyes/main.py tests/test_main.py
git commit -m "feat: wire capture/gaze/render/output into a backend-selecting main loop"
```

---

### Task 8: README and manual verification

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: nothing new — this documents how to run what Tasks 1–7 built.
- Produces: nothing further downstream; this is the final task.

- [ ] **Step 1: Write `README.md`**

```markdown
# Alien Gaze Rig

Screen eyes that track the nearest face. See `docs/build-sheet.md` for the hardware plan
and `docs/superpowers/specs/2026-09-07-alien-gaze-rig-design.md` for the software design.

## Setup (Mac, simulation mode)

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-common.txt

## Run (Mac, simulation mode)

    python -m alien_eyes.main --sim

A window opens showing both simulated eye panels tracking your face via the webcam.
Press `q` (with the window focused) or Ctrl-C to quit.

## Setup (Raspberry Pi)

    python3 -m venv .venv --system-site-packages   # picks up picamera2, installed via apt
    source .venv/bin/activate
    pip install -r requirements-pi.txt

Wire the two GC9A01 panels and camera per `docs/build-sheet.md` §3 before running.

## Run (Raspberry Pi)

    python -m alien_eyes.main --pi

Omitting `--sim`/`--pi` auto-detects: Pi hardware on a Raspberry Pi, sim mode otherwise.

## Tests

    pytest
```

- [ ] **Step 2: Manually verify the Mac simulation end-to-end**

Run: `python -m alien_eyes.main --sim`

Check each of the following, then press `q` to quit:
- A window opens showing two identical eye images side by side.
- Moving in front of the webcam, the pupils track your face with a slight, deliberate lag (not an instant snap).
- Stepping out of frame, the eyes switch to a slow idle scanning motion instead of freezing.
- Pressing `q` closes the window and the process exits cleanly (no traceback).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add setup and run instructions for Mac sim and Pi modes"
```
