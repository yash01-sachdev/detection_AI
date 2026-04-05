from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable

from app.types import BoundingBox, Detection

MONITORED_ZONE_TYPES = {"desk", "work_area"}
MONITORED_ENTITY_TYPES = {"person", "employee"}


@dataclass
class InactivityState:
    last_seen_at: float
    last_moved_at: float
    last_center: tuple[float, float]
    last_posture: str | None = None


class InactivityPostureAnalyzer:
    def __init__(
        self,
        *,
        inactivity_threshold_seconds: int,
        movement_threshold_px: float,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.inactivity_threshold_seconds = max(inactivity_threshold_seconds, 1)
        self.movement_threshold_px = max(movement_threshold_px, 1.0)
        self.clock = clock or monotonic
        self.stale_track_seconds = max(self.inactivity_threshold_seconds * 3, 15)
        self.states: dict[str, InactivityState] = {}

    def annotate(self, frame: Any, detections: list[Detection]) -> list[Detection]:
        now = self.clock()
        self._drop_stale_states(now)

        annotated: list[Detection] = []
        for detection in detections:
            annotated.append(self._annotate_detection(detection, now))
        return annotated

    def _annotate_detection(self, detection: Detection, now: float) -> Detection:
        if detection.track_id is None or detection.entity_type not in MONITORED_ENTITY_TYPES:
            return detection

        zone_type = str(detection.details.get("zone_type") or "").strip()
        track_id = detection.track_id
        center = _bbox_center(detection.bbox)
        state = self.states.get(track_id)

        if state is None:
            self.states[track_id] = InactivityState(
                last_seen_at=now,
                last_moved_at=now,
                last_center=center,
            )
            return _clear_inactivity_details(detection)

        state.last_seen_at = now
        moved_distance = _center_distance(center, state.last_center)
        state.last_center = center

        if zone_type not in MONITORED_ZONE_TYPES or moved_distance >= self.movement_threshold_px:
            state.last_moved_at = now
            state.last_posture = None
            return _clear_inactivity_details(detection)

        inactive_seconds = int(now - state.last_moved_at)
        if inactive_seconds < self.inactivity_threshold_seconds:
            state.last_posture = None
            return _clear_inactivity_details(detection)

        state.last_posture = "inactive"
        return detection.model_copy(
            update={
                "posture": "inactive",
                "details": {
                    **detection.details,
                    "posture": "inactive",
                    "inactive_seconds": inactive_seconds,
                    "posture_source": "movement_watch",
                },
            }
        )

    def _drop_stale_states(self, now: float) -> None:
        for track_id in list(self.states.keys()):
            state = self.states[track_id]
            if now - state.last_seen_at > self.stale_track_seconds:
                self.states.pop(track_id, None)


def build_posture_analyzer(
    *,
    inactivity_threshold_seconds: int,
    movement_threshold_px: float,
) -> InactivityPostureAnalyzer:
    return InactivityPostureAnalyzer(
        inactivity_threshold_seconds=inactivity_threshold_seconds,
        movement_threshold_px=movement_threshold_px,
    )


def _bbox_center(bbox: BoundingBox) -> tuple[float, float]:
    return ((bbox.x1 + bbox.x2) / 2, (bbox.y1 + bbox.y2) / 2)


def _center_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _clear_inactivity_details(detection: Detection) -> Detection:
    details = dict(detection.details)
    details.pop("posture", None)
    details.pop("inactive_seconds", None)
    details.pop("posture_source", None)
    return detection.model_copy(update={"posture": None, "details": details})
