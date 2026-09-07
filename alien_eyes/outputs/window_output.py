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
