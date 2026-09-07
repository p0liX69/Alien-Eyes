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
