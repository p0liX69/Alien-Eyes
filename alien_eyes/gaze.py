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
