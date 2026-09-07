# Alien Gaze Rig — Software Design

Date: 2026-09-07
Status: Approved for planning

## Purpose

Turn the [build sheet](../build-sheet.md) reference implementation into a real, testable
codebase for the Alien Gaze Rig — animated screen-eyes that track the nearest face. Parts
are on order but not yet assembled; the two GC9A01 panels and camera aren't wired up yet.
The immediate goal is to write and tune the core gaze-tracking logic now, on the Mac (via
webcam + an on-screen preview), and have it run unchanged on the Pi once hardware arrives —
swapping only how frames come in and where the eye image goes.

## Repo structure

```
Alien-Eyes/
  docs/
    build-sheet.md              # transcribed from the original PDF
    superpowers/specs/2026-09-07-alien-gaze-rig-design.md
  alien_eyes/
    capture.py                  # frame sources: webcam (Mac) / Pi camera
    gaze.py                     # face detect + smoothing + lock-on — pure logic, no hardware
    render.py                   # draws sclera/iris/pupil to a PIL image
    config.py                   # tunable constants (damping, colors, lock-on delay)
    outputs/
      window_output.py          # cv2.imshow window, for Mac sim
      spi_output.py              # GC9A01 driver, for Pi
    main.py                     # wires capture + gaze + render + output together
  tests/
    test_gaze.py                # unit tests for the pure logic
  requirements-common.txt       # opencv-python, pillow — installs on both Mac and Pi
  requirements-pi.txt           # adafruit-gc9a01a, board, busio, digitalio, picamera2
  README.md                     # setup + run instructions for both modes
```

The build sheet PDF is transcribed to Markdown rather than committed as a binary, so it's
diffable and linkable from other docs as the build evolves.

## Components & responsibilities

- **`capture.py`** — a minimal common interface: `read() -> grayscale frame or None`. Two
  implementations: `WebcamCapture` (`cv2.VideoCapture(0)`) and `PiCameraCapture`
  (`picamera2`). Neither knows anything about faces or rendering.
- **`gaze.py`** — a `GazeTracker` class, hardware-agnostic: takes a grayscale frame in,
  returns `(gx, gy)` out. Owns Haar cascade detection, the fallback idle scan, the
  damping/easing, and the §6 lock-on delay (require ~400ms on a face before switching
  targets). This is the module with real logic worth unit-testing.
- **`render.py`** — pure function `draw_eye(gx, gy, blink_amount=0.0) -> PIL.Image`, ports
  the build sheet's `draw_eye()`. Takes a `blink_amount` parameter now so the interface
  doesn't need to change when blink is implemented later, but `GazeTracker` always passes
  `0.0` for this pass (see Out of scope).
- **`outputs/`** — `push(image)` is the only method either implementation needs.
  `WindowOutput` shows one window with the image tiled twice side-by-side, mimicking the two
  physical panels. `SPIOutput` blits to both GC9A01 panels per the §3 pinout.
- **`main.py`** — picks capture + output backend via a `--sim` flag (defaults to sim on Mac,
  Pi on Linux+ARM if unspecified), then runs: capture → track → render → push.
- **`config.py`** — all magic numbers (DAMPING, LOCK_ON_MS, colors, panel size) in one place.

## Data flow / main loop

```
backend = pick_backend(args.sim)          # explicit flag wins; else auto-detect platform
capture = backend.capture()               # WebcamCapture() or PiCameraCapture()
output  = backend.output()                # WindowOutput() or SPIOutput()
tracker = GazeTracker()

while True:
    frame = capture.read()
    if frame is None: continue            # skip, don't crash
    gx, gy = tracker.update(frame)
    img = render.draw_eye(gx, gy)
    output.push(img)
```

Auto-detect: `sys.platform` plus checking `/proc/device-tree/model` for "Raspberry Pi" →
Pi backend; otherwise Mac sim. `--sim` / `--pi` flags override auto-detect, since forcing
sim mode while developing *on* a Pi over SSH (before displays are wired) is a real case.

## Error handling

- Capture/output backends fail fast at startup with a clear message if hardware init fails
  (camera not found, SPI panel not responding) — no silent partial operation.
- Mid-loop frame read failures are skipped, not fatal (`capture.read()` returning `None`
  just skips that iteration), matching the build sheet's "don't freeze" stance in §4.
- No untrusted external input to validate — this is a closed-loop hardware app, so the
  standard input-validation checklist mostly doesn't apply.

## Testing

- Unit tests (`tests/test_gaze.py`) cover `GazeTracker`'s pure logic: damping converges
  toward a goal, the lock-on delay doesn't switch targets on a single-frame face blip, and
  the fallback scan output stays within `[-1, 1]` bounds. These run on any machine, no
  camera/display required.
- **Scoped exception to the usual coverage bar:** `capture.py` and `outputs/` wrap
  hardware/OS calls directly and aren't meaningfully unit-testable — faking a camera or SPI
  panel to hit a coverage number wouldn't catch real problems. Verification there is manual:
  run `main.py --sim` on the Mac now, and `main.py --pi` on the Pi once wired per §3.

## Out of scope (for this pass)

- Blink, night-vision (IR), and the two-microcontroller escalation (§7) — noted in the build
  sheet as enhancements, not needed for a first working loop. Lock-on delay is included now
  since it's cheap and part of `GazeTracker`'s core job.
- Physical assembly, socket dry-fitting, wiring — hardware tasks tracked outside this repo's
  code, informational content lives in `build-sheet.md`.
