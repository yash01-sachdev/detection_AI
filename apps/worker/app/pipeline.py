import logging
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from app.camera import BaseCameraSource
from app.client import ApiClient
from app.detection import BaseDetector
from app.types import BoundingBox, Detection, ZoneDefinition

logger = logging.getLogger(__name__)


@dataclass
class TrackRecord:
    track_id: str
    entity_type: str
    center: tuple[float, float]
    bbox: BoundingBox
    missed_frames: int = 0


class StableTracker:
    def __init__(self, max_distance_px: float = 140.0, max_missed_frames: int = 6) -> None:
        self.max_distance_px = max_distance_px
        self.max_missed_frames = max_missed_frames
        self.next_track_number = 1
        self.tracks: dict[str, TrackRecord] = {}

    def assign_tracks(self, detections: list[Detection]) -> list[Detection]:
        if not detections:
            self._age_tracks(set())
            return []

        unmatched_indices = set(range(len(detections)))
        used_track_ids: set[str] = set()
        assignments: dict[int, str] = {}

        candidate_matches: list[tuple[float, str, int]] = []
        for track_id, track in self.tracks.items():
            for index, detection in enumerate(detections):
                if detection.entity_type != track.entity_type:
                    continue
                distance = _center_distance(track.center, _bbox_center(detection.bbox))
                if distance <= self.max_distance_px:
                    candidate_matches.append((distance, track_id, index))

        for _, track_id, index in sorted(candidate_matches, key=lambda item: item[0]):
            if track_id in used_track_ids or index not in unmatched_indices:
                continue
            assignments[index] = track_id
            used_track_ids.add(track_id)
            unmatched_indices.remove(index)

        self._age_tracks(used_track_ids)

        tracked_detections: list[Detection] = []
        for index, detection in enumerate(detections):
            track_id = assignments.get(index)
            is_new_track = False

            if track_id is None:
                track_id = self._create_track(detection)
                is_new_track = True
            else:
                self._update_track(track_id, detection)

            tracked_detections.append(
                detection.model_copy(
                    update={
                        "track_id": track_id,
                        "details": {
                            **detection.details,
                            "track_is_new": is_new_track,
                        },
                    }
                )
            )

        return tracked_detections

    def _create_track(self, detection: Detection) -> str:
        track_id = f"t{self.next_track_number}"
        self.next_track_number += 1
        self.tracks[track_id] = TrackRecord(
            track_id=track_id,
            entity_type=detection.entity_type,
            center=_bbox_center(detection.bbox),
            bbox=detection.bbox,
            missed_frames=0,
        )
        return track_id

    def _update_track(self, track_id: str, detection: Detection) -> None:
        self.tracks[track_id] = TrackRecord(
            track_id=track_id,
            entity_type=detection.entity_type,
            center=_bbox_center(detection.bbox),
            bbox=detection.bbox,
            missed_frames=0,
        )

    def _age_tracks(self, used_track_ids: set[str]) -> None:
        for track_id in list(self.tracks.keys()):
            if track_id in used_track_ids:
                continue
            track = self.tracks[track_id]
            track.missed_frames += 1
            if track.missed_frames > self.max_missed_frames:
                self.tracks.pop(track_id, None)


class NoopFaceRecognizer:
    def annotate(self, frame: Any, detections: list[Detection]) -> list[Detection]:
        return detections


class NoopPostureAnalyzer:
    def annotate(self, frame: Any, detections: list[Detection]) -> list[Detection]:
        return detections


class MonitoringPipeline:
    def __init__(
        self,
        source: BaseCameraSource,
        detector: BaseDetector,
        api_client: ApiClient,
        frame_stride: int,
        alert_cooldown_seconds: int,
        worker_name: str,
        camera_source_type: str,
        camera_source: str,
        preview_output_dir: str,
        snapshot_output_dir: str,
    ) -> None:
        self.source = source
        self.detector = detector
        self.api_client = api_client
        self.frame_stride = max(frame_stride, 1)
        self.alert_cooldown_seconds = max(alert_cooldown_seconds, 1)
        self.tracker = StableTracker()
        self.face_recognizer = NoopFaceRecognizer()
        self.posture_analyzer = NoopPostureAnalyzer()
        self.last_sent_at: dict[str, dict[str, float | str]] = {}
        self.worker_name = worker_name
        self.camera_source_type = camera_source_type
        self.camera_source = camera_source
        self.preview_dir = Path(preview_output_dir).resolve()
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        self.preview_frame_path = self.preview_dir / "latest_frame.jpg"
        self.preview_status_path = self.preview_dir / "status.json"
        self.snapshot_dir = Path(snapshot_output_dir).resolve()
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.zones: list[ZoneDefinition] = []
        self.last_zone_refresh_at = 0.0

    def run(self) -> None:
        frame_count = 0
        self._open_source()
        self._refresh_zones(force=True)

        try:
            while True:
                ok, frame = self.source.read()
                if not ok:
                    logger.warning("Unable to read frame from camera source.")
                    self._write_status(
                        camera_connected=False,
                        frame_count=frame_count,
                        last_detection_count=0,
                        last_labels=[],
                        message="Camera read failed. Retrying connection.",
                    )
                    self._reconnect_source()
                    continue

                frame_count += 1
                if frame_count % self.frame_stride != 0:
                    continue

                self._refresh_zones()
                detections = self.detector.detect(frame)
                detections = self.tracker.assign_tracks(detections)
                detections = self.face_recognizer.annotate(frame, detections)
                detections = self.posture_analyzer.annotate(frame, detections)
                detections = self._assign_zones(detections)
                self._persist_preview(frame, detections, frame_count)

                for detection in detections:
                    if not self._should_publish(detection):
                        continue
                    try:
                        snapshot_path = self._save_alert_snapshot(frame, detection)
                        self.api_client.ingest_detection(detection, snapshot_path=snapshot_path)
                    except Exception as exc:  # pragma: no cover
                        logger.warning("Failed to publish detection: %s", exc)

                if detections:
                    logger.info("Processed frame %s with %s detections.", frame_count, len(detections))
        finally:
            self.source.release()
            self._write_status(
                camera_connected=False,
                frame_count=frame_count,
                last_detection_count=0,
                last_labels=[],
                message="Worker stopped and camera was released.",
            )
            logger.info("Camera source released.")

    def _open_source(self) -> None:
        self.source.open()
        logger.info("Camera source opened. Starting monitoring loop.")
        self._write_status(
            camera_connected=True,
            frame_count=0,
            last_detection_count=0,
            last_labels=[],
            message="Camera opened. Waiting for detections.",
        )

    def _reconnect_source(self) -> None:
        try:
            self.source.release()
        except Exception:  # pragma: no cover
            pass

        sleep(2)
        try:
            self.source.open()
            logger.info("Camera source reopened after read failure.")
            self._write_status(
                camera_connected=True,
                frame_count=0,
                last_detection_count=0,
                last_labels=[],
                message="Camera reconnected. Waiting for detections.",
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to reopen camera source: %s", exc)

    def _should_publish(self, detection: Detection) -> bool:
        if detection.track_id is None:
            return False

        key = detection.track_id
        now = monotonic()
        zone_id = detection.zone_id or ""
        last_sent = self.last_sent_at.get(key)
        if last_sent is None:
            self.last_sent_at[key] = {"at": now, "zone_id": zone_id}
            return True

        last_zone_id = str(last_sent.get("zone_id", ""))
        if zone_id and zone_id != last_zone_id:
            self.last_sent_at[key] = {"at": now, "zone_id": zone_id}
            return True

        if not detection.details.get("track_is_new", False):
            return False
        self.last_sent_at[key] = {"at": now, "zone_id": zone_id}
        return True

    def _refresh_zones(self, force: bool = False) -> None:
        now = monotonic()
        if not force and now - self.last_zone_refresh_at < 15:
            return

        try:
            self.zones = self.api_client.fetch_zones()
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to refresh zones: %s", exc)
        finally:
            self.last_zone_refresh_at = now

    def _assign_zones(self, detections: list[Detection]) -> list[Detection]:
        if not self.zones:
            return detections

        annotated: list[Detection] = []
        for detection in detections:
            zone = self._match_zone(detection)
            if zone is None:
                annotated.append(detection)
                continue

            annotated.append(
                detection.model_copy(
                    update={
                        "zone_id": zone.id,
                        "details": {
                            **detection.details,
                            "zone_name": zone.name,
                            "zone_type": zone.zone_type,
                            "zone_restricted": zone.is_restricted,
                        },
                    }
                )
            )
        return annotated

    def _match_zone(self, detection: Detection) -> ZoneDefinition | None:
        point = _bbox_center(detection.bbox)
        candidates = [zone for zone in self.zones if _point_in_polygon(point, zone)]
        if not candidates:
            return None
        candidates.sort(key=lambda zone: (0 if zone.is_restricted else 1, _polygon_area(zone)))
        return candidates[0]

    def _persist_preview(
        self,
        frame: Any,
        detections: list[Detection],
        frame_count: int,
    ) -> None:
        import cv2

        preview_frame = frame.copy()
        labels: list[str] = []

        for detection in detections:
            zone_name = str(detection.details.get("zone_name", "")).strip()
            labels.append(
                f"{detection.identity or detection.label} @ {zone_name}"
                if zone_name
                else (detection.identity or detection.label)
            )
            x1 = int(detection.bbox.x1)
            y1 = int(detection.bbox.y1)
            x2 = int(detection.bbox.x2)
            y2 = int(detection.bbox.y2)
            cv2.rectangle(preview_frame, (x1, y1), (x2, y2), (26, 164, 132), 2)
            caption = f"{(detection.identity or detection.label).title()} {int(detection.confidence * 100)}%"
            if zone_name:
                caption = f"{caption} | {zone_name}"
            cv2.putText(
                preview_frame,
                caption,
                (x1, max(y1 - 10, 18)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (244, 239, 230),
                2,
                cv2.LINE_AA,
            )

        cv2.imwrite(str(self.preview_frame_path), preview_frame)
        message = "Watching for people, dogs, and vehicles."
        if detections:
            message = "Detections found in the current frame."

        self._write_status(
            camera_connected=True,
            frame_count=frame_count,
            last_detection_count=len(detections),
            last_labels=labels,
            message=message,
        )

    def _write_status(
        self,
        *,
        camera_connected: bool,
        frame_count: int,
        last_detection_count: int,
        last_labels: list[str],
        message: str,
    ) -> None:
        payload = {
            "worker_name": self.worker_name,
            "camera_source_type": self.camera_source_type,
            "camera_source": self.camera_source,
            "camera_connected": camera_connected,
            "frame_updated_at": datetime.now(UTC).isoformat(),
            "frame_count": frame_count,
            "last_detection_count": last_detection_count,
            "last_labels": last_labels,
            "message": message,
        }
        self.preview_status_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _save_alert_snapshot(self, frame: Any, detection: Detection) -> str | None:
        import cv2

        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        track_id = detection.track_id or "unknown"
        file_name = f"{timestamp}-{track_id}.jpg"
        file_path = self.snapshot_dir / file_name

        snapshot = frame.copy()
        x1 = int(detection.bbox.x1)
        y1 = int(detection.bbox.y1)
        x2 = int(detection.bbox.x2)
        y2 = int(detection.bbox.y2)
        cv2.rectangle(snapshot, (x1, y1), (x2, y2), (26, 164, 132), 2)

        zone_name = str(detection.details.get("zone_name", "")).strip()
        caption = f"{(detection.identity or detection.label).title()} {int(detection.confidence * 100)}%"
        if zone_name:
            caption = f"{caption} | {zone_name}"

        cv2.putText(
            snapshot,
            caption,
            (x1, max(y1 - 10, 18)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (244, 239, 230),
            2,
            cv2.LINE_AA,
        )

        if not cv2.imwrite(str(file_path), snapshot):
            return None

        return f"/media/snapshots/{file_name}"


def _bbox_center(bbox: BoundingBox) -> tuple[float, float]:
    return ((bbox.x1 + bbox.x2) / 2, (bbox.y1 + bbox.y2) / 2)


def _center_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _point_in_polygon(point: tuple[float, float], zone: ZoneDefinition) -> bool:
    if len(zone.points) < 3:
        return False

    x, y = point
    inside = False
    point_count = len(zone.points)
    for index in range(point_count):
        first = zone.points[index]
        second = zone.points[(index + 1) % point_count]
        intersects = ((first.y > y) != (second.y > y)) and (
            x < (second.x - first.x) * (y - first.y) / ((second.y - first.y) or 1e-9) + first.x
        )
        if intersects:
            inside = not inside
    return inside


def _polygon_area(zone: ZoneDefinition) -> float:
    if len(zone.points) < 3:
        return float("inf")

    area = 0.0
    for index, point in enumerate(zone.points):
        next_point = zone.points[(index + 1) % len(zone.points)]
        area += point.x * next_point.y
        area -= next_point.x * point.y
    return abs(area) / 2
