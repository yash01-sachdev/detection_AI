import logging
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Callable

from app.camera import BaseCameraSource
from app.client import ApiClient
from app.detection import BaseDetector
from app.types import BoundingBox, Detection, WorkerAssignmentDefinition, ZoneDefinition

logger = logging.getLogger(__name__)


@dataclass
class TrackRecord:
    track_id: str
    entity_type: str
    center: tuple[float, float]
    bbox: BoundingBox
    missed_frames: int = 0


@dataclass
class ZonePresenceRecord:
    presence_id: str
    zone_id: str
    entity_key: str
    entity_type: str
    center: tuple[float, float]
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
        assignment_signature: str,
        assignment_poll_seconds: int,
        status_publish_seconds: int,
        live_frame_upload_seconds: int,
        face_recognizer: Any | None = None,
        posture_analyzer: Any | None = None,
    ) -> None:
        self.source = source
        self.detector = detector
        self.api_client = api_client
        self.frame_stride = max(frame_stride, 1)
        self.alert_cooldown_seconds = max(alert_cooldown_seconds, 1)
        self.tracker = StableTracker()
        self.face_recognizer = face_recognizer or NoopFaceRecognizer()
        self.posture_analyzer = posture_analyzer or NoopPostureAnalyzer()
        self.track_state: dict[str, dict[str, str]] = {}
        self.track_identity_memory: dict[str, dict[str, object]] = {}
        self.pending_unknown_zone_alerts: dict[str, dict[str, object]] = {}
        self.zone_presence_counter = 1
        self.zone_presences: dict[str, ZonePresenceRecord] = {}
        self.zone_presence_max_missed_frames = 12
        self.unknown_zone_alert_delay_seconds = 2.5
        self.worker_name = worker_name
        self.camera_source_type = camera_source_type
        self.camera_source = camera_source
        self.preview_dir = Path(preview_output_dir).resolve()
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        self.preview_frame_path = self.preview_dir / "latest_frame.jpg"
        self.preview_status_path = self.preview_dir / "status.json"
        self.snapshot_dir = Path(snapshot_output_dir).resolve()
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.assignment_signature = assignment_signature
        self.assignment_poll_seconds = max(assignment_poll_seconds, 1)
        self.status_publish_seconds = max(status_publish_seconds, 1)
        self.live_frame_upload_seconds = max(live_frame_upload_seconds, 1)
        self.zones: list[ZoneDefinition] = []
        self.last_zone_refresh_at = 0.0
        self.last_assignment_check_at = 0.0
        self.last_status_publish_at = 0.0
        self.last_live_upload_at = 0.0

    def run(
        self,
        assignment_provider: Callable[[], WorkerAssignmentDefinition | None] | None = None,
    ) -> str:
        frame_count = 0
        self._open_source()
        self._refresh_zones(force=True)

        try:
            while True:
                if assignment_provider is not None:
                    next_assignment = self._poll_assignment(assignment_provider)
                    if next_assignment is not None:
                        logger.info("Worker assignment changed. Restarting runtime.")
                        return "assignment_changed"

                ok, frame = self.source.read()
                if not ok:
                    logger.warning("Unable to read frame from camera source.")
                    self._write_status(
                        camera_connected=False,
                        frame_count=frame_count,
                        last_detection_count=0,
                        last_labels=[],
                        message="Camera read failed. Retrying connection.",
                        force_publish=True,
                    )
                    self._reconnect_source()
                    continue

                frame_count += 1
                if frame_count % self.frame_stride != 0:
                    continue

                self._refresh_zones()
                detections = self.detector.detect(frame)
                detections = self.tracker.assign_tracks(detections)
                self._prune_track_identity_memory()
                detections = self.face_recognizer.annotate(frame, detections)
                detections = self._stabilize_identities(detections)
                detections = _deduplicate_detections(detections)
                detections = self._assign_zones(detections)
                detections = self.posture_analyzer.annotate(frame, detections)
                detections = self._assign_presence_sessions(detections)
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
                force_publish=True,
            )
            logger.info("Camera source released.")
        return "stopped"

    def _open_source(self) -> None:
        self.source.open()
        logger.info("Camera source opened. Starting monitoring loop.")
        self._write_status(
            camera_connected=True,
            frame_count=0,
            last_detection_count=0,
            last_labels=[],
            message="Camera opened. Waiting for detections.",
            force_publish=True,
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
                force_publish=True,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to reopen camera source: %s", exc)

    def _should_publish(self, detection: Detection) -> bool:
        presence_key = str(detection.details.get("presence_key", "")).strip()
        key = presence_key or detection.track_id
        if not key:
            return False

        zone_id = detection.zone_id or ""
        entity_key = _build_entity_key(detection)
        posture = detection.posture or ""
        zone_restricted = bool(detection.details.get("zone_restricted"))
        employee_id = str(detection.details.get("employee_id", "")).strip()
        is_unknown_zone_presence = bool(
            presence_key and zone_id and zone_restricted and detection.entity_type == "person" and not employee_id and not detection.identity
        )
        if presence_key and not is_unknown_zone_presence:
            self.pending_unknown_zone_alerts.pop(presence_key, None)
        last_state = self.track_state.get(key)

        current_state = {
            "zone_id": zone_id,
            "entity_key": entity_key,
            "posture": posture,
        }

        if last_state is None:
            self.track_state[key] = current_state
            if is_unknown_zone_presence:
                return self._should_publish_unknown_zone_presence(presence_key)
            return True

        last_zone_id = str(last_state.get("zone_id", ""))
        last_entity_key = str(last_state.get("entity_key", ""))
        last_posture = str(last_state.get("posture", ""))

        if entity_key and entity_key != last_entity_key:
            self.track_state[key] = current_state
            return True

        if zone_id and zone_id != last_zone_id:
            self.track_state[key] = current_state
            return True

        if posture != last_posture:
            self.track_state[key] = current_state
            return bool(posture)

        self.track_state[key] = current_state
        if is_unknown_zone_presence:
            return self._should_publish_unknown_zone_presence(presence_key)
        if presence_key:
            return False
        if not detection.details.get("track_is_new", False):
            return False
        return True

    def _refresh_zones(self, force: bool = False) -> None:
        now = monotonic()
        if not force and now - self.last_zone_refresh_at < 5:
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
            posture_suffix = _posture_suffix(detection)
            labels.append(
                f"{detection.identity or detection.label}{posture_suffix} @ {zone_name}"
                if zone_name
                else f"{detection.identity or detection.label}{posture_suffix}"
            )
            x1 = int(detection.bbox.x1)
            y1 = int(detection.bbox.y1)
            x2 = int(detection.bbox.x2)
            y2 = int(detection.bbox.y2)
            cv2.rectangle(preview_frame, (x1, y1), (x2, y2), (26, 164, 132), 2)
            caption = f"{(detection.identity or detection.label).title()} {int(detection.confidence * 100)}%"
            if zone_name:
                caption = f"{caption} | {zone_name}"
            posture_label = _posture_label(detection)
            if posture_label:
                caption = f"{caption} | {posture_label}"
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

        published_frame_at = self._publish_live_frame_if_due()
        self._write_status(
            camera_connected=True,
            frame_count=frame_count,
            last_detection_count=len(detections),
            last_labels=labels,
            message=message,
            publish_remote=published_frame_at is not None,
            frame_updated_at=published_frame_at,
        )

    def _assign_presence_sessions(self, detections: list[Detection]) -> list[Detection]:
        if not detections:
            self._age_presence_sessions(set())
            return detections

        annotated: list[Detection] = []
        used_presence_ids: set[str] = set()
        for detection in detections:
            if not detection.zone_id:
                annotated.append(detection)
                continue

            entity_key = _build_entity_key(detection)
            presence = self._find_presence_session(detection, entity_key, used_presence_ids)
            is_new_presence = False
            center = _bbox_center(detection.bbox)

            if presence is None:
                presence = self._create_presence_session(detection.zone_id, entity_key, detection.entity_type, center)
                is_new_presence = True
            else:
                presence.center = center
                presence.missed_frames = 0

            used_presence_ids.add(presence.presence_id)
            annotated.append(
                detection.model_copy(
                    update={
                        "details": {
                            **detection.details,
                            "presence_key": presence.presence_id,
                            "presence_is_new": is_new_presence,
                        }
                    }
                )
            )

        self._age_presence_sessions(used_presence_ids)
        return annotated

    def _stabilize_identities(self, detections: list[Detection]) -> list[Detection]:
        stabilized: list[Detection] = []
        for detection in detections:
            if not detection.track_id:
                stabilized.append(detection)
                continue

            memory = self.track_identity_memory.get(detection.track_id)
            employee_id = str(detection.details.get("employee_id", "")).strip()
            known_person_id = str(detection.details.get("known_person_id", "")).strip()
            if detection.entity_type in {"employee", "known_person"} and ((employee_id or known_person_id) or detection.identity):
                self.track_identity_memory[detection.track_id] = {
                    "entity_type": detection.entity_type,
                    "identity": detection.identity,
                    "employee_id": detection.details.get("employee_id"),
                    "employee_code": detection.details.get("employee_code"),
                    "role_title": detection.details.get("role_title"),
                    "known_person_id": detection.details.get("known_person_id"),
                    "known_person_name": detection.details.get("known_person_name"),
                }
                stabilized.append(detection)
                continue

            if detection.entity_type == "person" and memory:
                updated_details = {**detection.details}
                for key in ("employee_id", "employee_code", "role_title", "known_person_id", "known_person_name"):
                    value = memory.get(key)
                    if value:
                        updated_details[key] = value
                stabilized.append(
                    detection.model_copy(
                        update={
                            "entity_type": str(memory.get("entity_type") or "person"),
                            "identity": str(memory.get("identity") or detection.identity or "").strip() or detection.identity,
                            "details": updated_details,
                        }
                    )
                )
                continue

            stabilized.append(detection)

        return stabilized

    def _prune_track_identity_memory(self) -> None:
        active_track_ids = set(self.tracker.tracks.keys())
        for track_id in list(self.track_identity_memory.keys()):
            if track_id not in active_track_ids:
                self.track_identity_memory.pop(track_id, None)

    def _find_presence_session(
        self,
        detection: Detection,
        entity_key: str,
        used_presence_ids: set[str],
    ) -> ZonePresenceRecord | None:
        if not detection.zone_id:
            return None

        center = _bbox_center(detection.bbox)
        candidates = [
            presence
            for presence in self.zone_presences.values()
            if presence.zone_id == detection.zone_id
            and presence.entity_type == detection.entity_type
            and presence.presence_id not in used_presence_ids
        ]
        if not candidates:
            return None

        if entity_key.startswith("employee:") or entity_key.startswith("identity:"):
            for presence in candidates:
                if presence.entity_key == entity_key:
                    return presence
            return None

        best_match: ZonePresenceRecord | None = None
        best_distance = float("inf")
        for presence in candidates:
            if presence.entity_key != entity_key:
                continue
            distance = _center_distance(center, presence.center)
            if distance <= 160 and distance < best_distance:
                best_match = presence
                best_distance = distance
        return best_match

    def _create_presence_session(
        self,
        zone_id: str,
        entity_key: str,
        entity_type: str,
        center: tuple[float, float],
    ) -> ZonePresenceRecord:
        presence_id = f"p{self.zone_presence_counter}"
        self.zone_presence_counter += 1
        presence = ZonePresenceRecord(
            presence_id=presence_id,
            zone_id=zone_id,
            entity_key=entity_key,
            entity_type=entity_type,
            center=center,
            missed_frames=0,
        )
        self.zone_presences[presence_id] = presence
        return presence

    def _age_presence_sessions(self, matched_presence_ids: set[str]) -> None:
        for presence_id in list(self.zone_presences.keys()):
            presence = self.zone_presences[presence_id]
            if presence_id in matched_presence_ids:
                presence.missed_frames = 0
                continue
            presence.missed_frames += 1
            if presence.missed_frames > self.zone_presence_max_missed_frames:
                self.zone_presences.pop(presence_id, None)
                self.pending_unknown_zone_alerts.pop(presence_id, None)

    def _should_publish_unknown_zone_presence(self, presence_key: str) -> bool:
        now = monotonic()
        pending = self.pending_unknown_zone_alerts.get(presence_key)
        if pending is None:
            self.pending_unknown_zone_alerts[presence_key] = {
                "first_seen_at": now,
                "published": False,
            }
            return False

        if bool(pending.get("published")):
            return False

        first_seen_at = float(pending.get("first_seen_at") or now)
        if now - first_seen_at < self.unknown_zone_alert_delay_seconds:
            return False

        pending["published"] = True
        return True

    def _write_status(
        self,
        *,
        camera_connected: bool,
        frame_count: int,
        last_detection_count: int,
        last_labels: list[str],
        message: str,
        force_publish: bool = False,
        publish_remote: bool = True,
        frame_updated_at: datetime | None = None,
    ) -> None:
        now = monotonic()
        local_frame_updated_at = frame_updated_at or datetime.now(UTC)
        payload = {
            "worker_name": self.worker_name,
            "camera_source_type": self.camera_source_type,
            "camera_source": self.camera_source,
            "camera_connected": camera_connected,
            "frame_updated_at": local_frame_updated_at.isoformat(),
            "frame_count": frame_count,
            "last_detection_count": last_detection_count,
            "last_labels": last_labels,
            "message": message,
        }
        self.preview_status_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        if publish_remote and (force_publish or now - self.last_status_publish_at >= self.status_publish_seconds):
            try:
                self.api_client.publish_worker_status(
                    camera_connected=camera_connected,
                    camera_source_type=self.camera_source_type,
                    camera_source=self.camera_source,
                    frame_count=frame_count,
                    last_detection_count=last_detection_count,
                    last_labels=last_labels,
                    message=message,
                    frame_updated_at=frame_updated_at.isoformat() if frame_updated_at is not None else None,
                )
                self.last_status_publish_at = now
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to publish worker status: %s", exc)

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
        posture_label = _posture_label(detection)
        if posture_label:
            caption = f"{caption} | {posture_label}"

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

        try:
            uploaded_path = self.api_client.upload_snapshot(str(file_path))
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to upload alert snapshot: %s", exc)
            return None
        return uploaded_path or None

    def _publish_live_frame_if_due(self) -> datetime | None:
        now = monotonic()
        if now - self.last_live_upload_at < self.live_frame_upload_seconds:
            return None

        try:
            self.api_client.upload_live_frame(str(self.preview_frame_path))
            self.last_live_upload_at = now
            return datetime.now(UTC)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to upload live frame: %s", exc)
            return None

    def _poll_assignment(
        self,
        assignment_provider: Callable[[], WorkerAssignmentDefinition | None],
    ) -> WorkerAssignmentDefinition | None:
        now = monotonic()
        if now - self.last_assignment_check_at < self.assignment_poll_seconds:
            return None

        self.last_assignment_check_at = now
        assignment = assignment_provider()
        if assignment is None:
            return WorkerAssignmentDefinition(worker_name=self.worker_name, is_active=False)
        if assignment.signature() != self.assignment_signature:
            return assignment
        return None


def _bbox_center(bbox: BoundingBox) -> tuple[float, float]:
    return ((bbox.x1 + bbox.x2) / 2, (bbox.y1 + bbox.y2) / 2)


def _center_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _deduplicate_detections(detections: list[Detection]) -> list[Detection]:
    if len(detections) < 2:
        return detections

    kept: list[Detection] = []
    for detection in sorted(detections, key=_detection_sort_key, reverse=True):
        overlaps_existing = False
        for existing in kept:
            if detection.entity_type not in {"person", "employee"} or existing.entity_type not in {"person", "employee"}:
                continue
            if _bbox_iou(detection.bbox, existing.bbox) >= 0.45 or _boxes_likely_same_subject(detection.bbox, existing.bbox):
                overlaps_existing = True
                break
        if not overlaps_existing:
            kept.append(detection)
    return kept


def _detection_sort_key(detection: Detection) -> tuple[int, int, float, float]:
    has_identity = 1 if detection.identity else 0
    is_employee = 1 if detection.entity_type == "employee" else 0
    area = _bbox_area(detection.bbox)
    return (has_identity, is_employee, detection.confidence, area)


def _build_entity_key(detection: Detection) -> str:
    employee_id = str(detection.details.get("employee_id", "")).strip()
    if employee_id:
        return f"employee:{employee_id}"
    known_person_id = str(detection.details.get("known_person_id", "")).strip()
    if known_person_id:
        return f"known_person:{known_person_id}"
    if detection.identity:
        return f"identity:{detection.identity.lower()}"
    return detection.entity_type


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


def _bbox_area(bbox: BoundingBox) -> float:
    return max(0.0, bbox.x2 - bbox.x1) * max(0.0, bbox.y2 - bbox.y1)


def _bbox_iou(first: BoundingBox, second: BoundingBox) -> float:
    x_left = max(first.x1, second.x1)
    y_top = max(first.y1, second.y1)
    x_right = min(first.x2, second.x2)
    y_bottom = min(first.y2, second.y2)

    intersection_width = max(0.0, x_right - x_left)
    intersection_height = max(0.0, y_bottom - y_top)
    intersection = intersection_width * intersection_height
    if intersection <= 0:
        return 0.0

    union = _bbox_area(first) + _bbox_area(second) - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def _boxes_likely_same_subject(first: BoundingBox, second: BoundingBox) -> bool:
    first_center = _bbox_center(first)
    second_center = _bbox_center(second)
    center_distance = _center_distance(first_center, second_center)
    largest_dimension = max(
        first.x2 - first.x1,
        first.y2 - first.y1,
        second.x2 - second.x1,
        second.y2 - second.y1,
        1.0,
    )
    return center_distance <= largest_dimension * 0.35


def _posture_suffix(detection: Detection) -> str:
    posture_label = _posture_label(detection)
    return f" ({posture_label})" if posture_label else ""


def _posture_label(detection: Detection) -> str:
    if detection.posture == "inactive":
        inactive_seconds = int(detection.details.get("inactive_seconds") or 0)
        return f"{inactive_seconds}s inactive" if inactive_seconds else "inactive"
    if detection.posture == "head_down":
        return "head down"
    return ""
