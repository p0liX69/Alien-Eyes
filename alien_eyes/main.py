# alien_eyes/main.py
import argparse
import time

from alien_eyes import config, render
from alien_eyes.gaze import GazeTracker


def is_raspberry_pi():
    try:
        with open("/proc/device-tree/model") as f:
            return "raspberry pi" in f.read().lower()
    except OSError:
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
    frame_budget = 1.0 / config.TARGET_FPS
    try:
        while not output.should_quit():
            frame_start = time.perf_counter()
            frame = capture.read()
            if frame is None:
                continue
            gx, gy = tracker.update(frame)
            img = render.draw_eye(gx, gy)
            output.push(img)
            remaining = frame_budget - (time.perf_counter() - frame_start)
            if remaining > 0:
                time.sleep(remaining)
    finally:
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
