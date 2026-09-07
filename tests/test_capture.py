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
