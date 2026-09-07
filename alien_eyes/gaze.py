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
        face_lost_grace_ms=config.FACE_LOST_GRACE_MS,
        cascade_path=None,
    ):
        self.damping = damping
        self.lock_on_ms = lock_on_ms
        self.switch_threshold = switch_threshold
        self.face_lost_grace_ms = face_lost_grace_ms

        self.tx = 0.0
        self.ty = 0.0
        self._lock_goal = None
        self._pending_goal = None
        self._pending_since = None
        self._lost_since = None

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
            self._lost_since = None
            target = self._lock_goal
        elif self._lock_goal is not None and self._within_lost_grace(now):
            # Detector dropout (e.g. a Haar cascade flickering frame-to-frame on a
            # stationary face) — hold the last known position instead of snapping
            # toward the idle scan.
            target = self._lock_goal
        else:
            self._lock_goal = None
            self._pending_goal = None
            self._pending_since = None
            self._lost_since = None
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

    def _within_lost_grace(self, now):
        if self._lost_since is None:
            self._lost_since = now
        return now - self._lost_since < self.face_lost_grace_ms / 1000.0

    def _fallback_goal(self, now):
        return (
            math.sin(now * config.FALLBACK_SCAN_SPEED_X) * config.FALLBACK_SCAN_AMPLITUDE_X,
            math.sin(now * config.FALLBACK_SCAN_SPEED_Y) * config.FALLBACK_SCAN_AMPLITUDE_Y,
        )
