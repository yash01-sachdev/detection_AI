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

        self.capture = cv2.VideoCapture(self.camera_index)

    def read(self) -> tuple[bool, Any]:
        if self.capture is None:
            raise RuntimeError("Camera source is not open.")
        return self.capture.read()

    def release(self) -> None:
        if self.capture is not None:
            self.capture.release()


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

