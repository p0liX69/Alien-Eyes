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
