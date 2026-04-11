from abc import ABC, abstractmethod
from typing import Any

from app.config import Settings


class BaseCameraSource(ABC):
    @abstractmethod
    def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def read(self) -> tuple[bool, Any]:
        raise NotImplementedError

    @abstractmethod
    def release(self) -> None:
        raise NotImplementedError


class WebcamSource(BaseCameraSource):
    def __init__(self, camera_index: int) -> None:
        self.camera_index = camera_index
        self.capture = None

    def open(self) -> None:
        import cv2

        candidate_indices = [self.camera_index]
        candidate_indices.extend(index for index in range(4) if index != self.camera_index)
        candidates: list[tuple[str, int | None]] = [
            ("directshow", getattr(cv2, "CAP_DSHOW", None)),
            ("media_foundation", getattr(cv2, "CAP_MSMF", None)),
            ("default", None),
        ]

        for candidate_index in candidate_indices:
            for _, backend in candidates:
                capture = None
                try:
                    capture = (
                        cv2.VideoCapture(candidate_index, backend)
                        if backend is not None
                        else cv2.VideoCapture(candidate_index)
                    )
                    if not capture or not capture.isOpened():
                        continue

                    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    if hasattr(cv2, "CAP_PROP_FOURCC"):
                        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

                    frame = self._warmup(capture)
                    if frame is not None and self._frame_has_signal(frame):
                        self.capture = capture
                        self.camera_index = candidate_index
                        return
                except Exception:
                    pass
                finally:
                    if capture is not None and capture is not self.capture:
                        capture.release()

        raise RuntimeError(f"Unable to open a usable webcam feed for index {self.camera_index}.")

    def read(self) -> tuple[bool, Any]:
        if self.capture is None:
            raise RuntimeError("Camera source is not open.")

        ok, frame = self.capture.read()
        if ok and self._frame_has_signal(frame):
            return ok, frame

        for _ in range(2):
            ok, frame = self.capture.read()
            if ok and self._frame_has_signal(frame):
                return ok, frame

        return False, None

    def release(self) -> None:
        if self.capture is not None:
            self.capture.release()

    def _warmup(self, capture) -> Any | None:
        last_frame = None
        for _ in range(8):
            ok, frame = capture.read()
            if ok:
                last_frame = frame
        return last_frame

    @staticmethod
    def _frame_has_signal(frame: Any) -> bool:
        if frame is None:
            return False
        try:
            overall_std = float(frame.std())
            if overall_std < 5.0:
                return False

            channel_min = frame.min(axis=(0, 1))
            channel_max = frame.max(axis=(0, 1))
            dynamic_range = channel_max - channel_min
            if float(dynamic_range.max()) < 15.0:
                return False

            channel_std = frame.std(axis=(0, 1))
            return float(channel_std.max()) >= 4.0
        except Exception:
            return False


class StreamSource(BaseCameraSource):
    def __init__(self, stream_url: str) -> None:
        self.stream_url = stream_url
        self.capture = None

    def open(self) -> None:
        import cv2

        self.capture = cv2.VideoCapture(self.stream_url)

    def read(self) -> tuple[bool, Any]:
        if self.capture is None:
            raise RuntimeError("Camera source is not open.")
        return self.capture.read()

    def release(self) -> None:
        if self.capture is not None:
            self.capture.release()


def build_camera_source(settings: Settings) -> BaseCameraSource:
    if settings.camera_source_type == "webcam":
        return WebcamSource(int(settings.camera_source))

    if settings.camera_source_type in {"droidcam", "rtsp", "uploaded_video"}:
        return StreamSource(settings.camera_source)

    raise ValueError(f"Unsupported camera source type: {settings.camera_source_type}")
