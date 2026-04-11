import logging
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from urllib.parse import urljoin

import httpx

from app.client import ApiClient
from app.config import Settings
from app.types import BoundingBox, Detection, EmployeeDefinition

logger = logging.getLogger(__name__)

MODEL_URLS = {
    "yunet": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "sface": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


@dataclass
class KnownFace:
    employee_id: str
    employee_code: str
    full_name: str
    role_title: str
    embedding: object


@dataclass
class RecognizedFace:
    bbox: tuple[float, float, float, float]
    employee_id: str
    employee_code: str
    full_name: str
    role_title: str
    score: float


class EmployeeFaceRecognizer:
    def __init__(
        self,
        api_client: ApiClient,
        api_base_url: str,
        model_dir: str,
        refresh_seconds: int,
        match_threshold: float,
    ) -> None:
        import cv2

        self.api_client = api_client
        self.api_root = api_base_url.replace("/api/v1", "")
        self.model_dir = Path(model_dir).resolve()
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.refresh_seconds = max(refresh_seconds, 15)
        self.match_threshold = match_threshold
        self.detector = None
        self.recognizer = None
        self.cv2 = cv2
        self.known_faces: list[KnownFace] = []
        self.last_refresh_at = 0.0

        try:
            self._ensure_models()
            self.detector = self.cv2.FaceDetectorYN_create(
                str(self.model_dir / "face_detection_yunet_2023mar.onnx"),
                "",
                (320, 320),
            )
            self.recognizer = self.cv2.FaceRecognizerSF_create(
                str(self.model_dir / "face_recognition_sface_2021dec.onnx"),
                "",
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Face recognition models are unavailable: %s", exc)
            self.detector = None
            self.recognizer = None

    def annotate(self, frame, detections: list[Detection]) -> list[Detection]:
        if self.detector is None or self.recognizer is None or not detections:
            return detections

        try:
            self._refresh_known_faces()
            if not self.known_faces:
                return detections

            faces = self._recognize_faces(frame)
        except Exception as exc:  # pragma: no cover
            logger.warning("Face recognition skipped for this frame: %s", exc)
            return detections
        if not faces:
            return detections

        annotated: list[Detection] = []
        for detection in detections:
            if detection.entity_type != "person":
                annotated.append(detection)
                continue

            match = _find_face_match_for_detection(detection, faces)
            if match is None:
                annotated.append(detection)
                continue

            annotated.append(
                detection.model_copy(
                    update={
                        "entity_type": "employee",
                        "identity": match.full_name,
                        "details": {
                            **detection.details,
                            "employee_id": match.employee_id,
                            "employee_code": match.employee_code,
                            "role_title": match.role_title,
                            "face_match_score": round(match.score, 4),
                        },
                    }
                )
            )

        return annotated

    def _refresh_known_faces(self) -> None:
        now = monotonic()
        if now - self.last_refresh_at < self.refresh_seconds:
            return

        self.last_refresh_at = now
        try:
            employees = self.api_client.fetch_employees()
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to refresh employee face profiles: %s", exc)
            return

        known_faces: list[KnownFace] = []
        for employee in employees:
            known_faces.extend(self._build_known_faces_for_employee(employee))

        self.known_faces = known_faces

    def _build_known_faces_for_employee(self, employee: EmployeeDefinition) -> list[KnownFace]:
        if self.detector is None or self.recognizer is None:
            return []

        known_faces: list[KnownFace] = []
        for profile in employee.face_profiles:
            image = self._download_profile_image(profile.source_image_path)
            if image is None:
                continue

            face = self._detect_primary_face(image)
            if face is None:
                logger.warning("No face found in enrollment image for employee %s.", employee.employee_code)
                continue

            aligned = self.recognizer.alignCrop(image, face)
            embedding = self.recognizer.feature(aligned)
            known_faces.append(
                KnownFace(
                    employee_id=employee.id,
                    employee_code=employee.employee_code,
                    full_name=_employee_display_name(employee),
                    role_title=employee.role_title,
                    embedding=embedding,
                )
            )

        return known_faces

    def _download_profile_image(self, source_image_path: str):
        import numpy as np

        url = source_image_path
        if not source_image_path.startswith("http"):
            url = urljoin(f"{self.api_root}/", source_image_path.lstrip("/"))

        try:
            response = httpx.get(url, timeout=20.0)
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover
            logger.warning("Unable to download enrollment image %s: %s", source_image_path, exc)
            return None

        image = self.cv2.imdecode(np.frombuffer(response.content, dtype=np.uint8), self.cv2.IMREAD_COLOR)
        return image

    def _detect_primary_face(self, image):
        self.detector.setInputSize((image.shape[1], image.shape[0]))
        _, faces = self.detector.detect(image)
        if faces is None or len(faces) == 0:
            return None
        return max(faces, key=lambda row: float(row[2] * row[3]))

    def _recognize_faces(self, frame) -> list[RecognizedFace]:
        self.detector.setInputSize((frame.shape[1], frame.shape[0]))
        _, faces = self.detector.detect(frame)
        if faces is None or len(faces) == 0:
            return []

        matches: list[RecognizedFace] = []
        for face in faces:
            aligned = self.recognizer.alignCrop(frame, face)
            embedding = self.recognizer.feature(aligned)
            best_match = _best_known_face_match(
                embedding=embedding,
                known_faces=self.known_faces,
                recognizer=self.recognizer,
                cv2_module=self.cv2,
                threshold=self.match_threshold,
            )
            if best_match is None:
                continue

            x, y, w, h = [float(value) for value in face[:4]]
            matches.append(
                RecognizedFace(
                    bbox=(x, y, w, h),
                    employee_id=best_match.employee_id,
                    employee_code=best_match.employee_code,
                    full_name=best_match.full_name,
                    role_title=best_match.role_title,
                    score=best_match.score,
                )
            )

        return matches

    def _ensure_models(self) -> None:
        for file_name, url in {
            "face_detection_yunet_2023mar.onnx": MODEL_URLS["yunet"],
            "face_recognition_sface_2021dec.onnx": MODEL_URLS["sface"],
        }.items():
            target = self.model_dir / file_name
            if target.exists() and target.stat().st_size > 1024:
                continue

            logger.info("Downloading face model %s.", file_name)
            response = httpx.get(url, timeout=60.0, follow_redirects=True)
            response.raise_for_status()
            if _looks_like_git_lfs_pointer(response.content):
                raise RuntimeError(f"Downloaded a Git LFS pointer instead of the {file_name} model.")
            target.write_bytes(response.content)


def build_face_recognizer(settings: Settings, api_client: ApiClient) -> EmployeeFaceRecognizer | None:
    recognizer = EmployeeFaceRecognizer(
        api_client=api_client,
        api_base_url=settings.api_base_url,
        model_dir=settings.face_model_dir,
        refresh_seconds=settings.face_profile_refresh_seconds,
        match_threshold=settings.face_match_threshold,
    )
    if recognizer.detector is None or recognizer.recognizer is None:
        logger.warning("Face recognition is unavailable. Continuing without employee matching.")
        return None

    return recognizer


@dataclass
class MatchResult:
    employee_id: str
    employee_code: str
    full_name: str
    role_title: str
    score: float


def _best_known_face_match(embedding, known_faces: list[KnownFace], recognizer, cv2_module, threshold: float) -> MatchResult | None:
    best_result: MatchResult | None = None
    for known_face in known_faces:
        score = float(recognizer.match(embedding, known_face.embedding, cv2_module.FaceRecognizerSF_FR_COSINE))
        if score < threshold:
            continue
        if best_result is None or score > best_result.score:
            best_result = MatchResult(
                employee_id=known_face.employee_id,
                employee_code=known_face.employee_code,
                full_name=known_face.full_name,
                role_title=known_face.role_title,
                score=score,
            )
    return best_result


def _find_face_match_for_detection(detection: Detection, faces: list[RecognizedFace]) -> RecognizedFace | None:
    person_box = detection.bbox
    candidates = [
        face
        for face in faces
        if _point_inside_bbox(
            (face.bbox[0] + face.bbox[2] / 2, face.bbox[1] + face.bbox[3] / 2),
            person_box,
        )
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda face: face.score, reverse=True)
    return candidates[0]


def _point_inside_bbox(point: tuple[float, float], bbox: BoundingBox) -> bool:
    return bbox.x1 <= point[0] <= bbox.x2 and bbox.y1 <= point[1] <= bbox.y2


def _employee_display_name(employee: EmployeeDefinition) -> str:
    full_name = f"{employee.first_name} {employee.last_name}".strip()
    return full_name or employee.employee_code


def _looks_like_git_lfs_pointer(content: bytes) -> bool:
    return content.startswith(b"version https://git-lfs.github.com/spec")
