from dataclasses import dataclass
from math import atan2, degrees
from time import monotonic
from typing import Any, Callable

from app.pose import BasePoseEstimator, NoopPoseEstimator, PoseDetection
from app.types import BoundingBox, Detection

INACTIVITY_ZONE_TYPES = {"desk", "work_area"}
HEAD_DOWN_ZONE_TYPES = {"desk"}
MONITORED_ENTITY_TYPES = {"person", "employee"}
POSE_MATCH_IOU_THRESHOLD = 0.2
POSE_RESET_SECONDS = 2.0


@dataclass
class TrackPostureState:
    last_seen_at: float
    last_moved_at: float
    last_center: tuple[float, float]
    pose_candidate: str | None = None
    pose_candidate_since: float | None = None
    active_pose: str | None = None
    pose_missing_since: float | None = None


class PostureAnalyzer:
    def __init__(
        self,
        *,
        pose_estimator: BasePoseEstimator | None = None,
        head_down_threshold_seconds: int,
        fall_threshold_seconds: int,
        inactivity_threshold_seconds: int,
        movement_threshold_px: float,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.pose_estimator = pose_estimator or NoopPoseEstimator()
        self.head_down_threshold_seconds = max(head_down_threshold_seconds, 1)
        self.fall_threshold_seconds = max(fall_threshold_seconds, 1)
        self.inactivity_threshold_seconds = max(inactivity_threshold_seconds, 1)
        self.movement_threshold_px = max(movement_threshold_px, 1.0)
        self.clock = clock or monotonic
        self.stale_track_seconds = max(self.inactivity_threshold_seconds * 3, 15)
        self.states: dict[str, TrackPostureState] = {}

    def annotate(self, frame: Any, detections: list[Detection]) -> list[Detection]:
        now = self.clock()
        self._drop_stale_states(now)
        pose_matches = _match_pose_detections(detections, self.pose_estimator.estimate(frame))

        annotated: list[Detection] = []
        for index, detection in enumerate(detections):
            pose_match = pose_matches.get(index)
            annotated.append(self._annotate_detection(detection, pose_match, now))
        return annotated

    def _annotate_detection(
        self,
        detection: Detection,
        pose_match: PoseDetection | None,
        now: float,
    ) -> Detection:
        if detection.track_id is None or detection.entity_type not in MONITORED_ENTITY_TYPES:
            return _clear_posture_details(detection)

        zone_type = str(detection.details.get("zone_type") or "").strip()
        track_id = detection.track_id
        center = _bbox_center(detection.bbox)
        state = self.states.get(track_id)

        if state is None:
            state = TrackPostureState(
                last_seen_at=now,
                last_moved_at=now,
                last_center=center,
            )
            self.states[track_id] = state

        moved_distance = _center_distance(center, state.last_center)
        state.last_seen_at = now
        state.last_center = center
        if moved_distance >= self.movement_threshold_px:
            state.last_moved_at = now

        instant_pose = _classify_pose(detection, pose_match)
        self._update_pose_state(state, instant_pose, pose_match is not None, now)

        if state.active_pose is not None:
            hold_seconds = (
                now - state.pose_candidate_since
                if state.pose_candidate_since is not None
                else 0.0
            )
            return _apply_pose_posture(
                detection=detection,
                posture=state.active_pose,
                hold_seconds=hold_seconds,
                pose_match=pose_match,
            )

        if zone_type in INACTIVITY_ZONE_TYPES and moved_distance < self.movement_threshold_px:
            inactive_seconds = int(now - state.last_moved_at)
            if inactive_seconds >= self.inactivity_threshold_seconds:
                return _apply_inactivity_posture(detection, inactive_seconds)

        return _clear_posture_details(detection)

    def _update_pose_state(
        self,
        state: TrackPostureState,
        instant_pose: str | None,
        pose_present: bool,
        now: float,
    ) -> None:
        if instant_pose is not None:
            state.pose_missing_since = None
            if state.pose_candidate != instant_pose:
                state.pose_candidate = instant_pose
                state.pose_candidate_since = now
            threshold = (
                self.fall_threshold_seconds
                if instant_pose == "fallen"
                else self.head_down_threshold_seconds
            )
            if state.pose_candidate_since is not None and now - state.pose_candidate_since >= threshold:
                state.active_pose = instant_pose
            return

        state.pose_candidate = None
        state.pose_candidate_since = None

        if state.active_pose is None:
            state.pose_missing_since = None
            return

        if pose_present:
            state.active_pose = None
            state.pose_missing_since = None
            return

        if state.pose_missing_since is None:
            state.pose_missing_since = now
            return

        if now - state.pose_missing_since >= POSE_RESET_SECONDS:
            state.active_pose = None
            state.pose_missing_since = None

    def _drop_stale_states(self, now: float) -> None:
        for track_id in list(self.states.keys()):
            state = self.states[track_id]
            if now - state.last_seen_at > self.stale_track_seconds:
                self.states.pop(track_id, None)


InactivityPostureAnalyzer = PostureAnalyzer


def build_posture_analyzer(
    *,
    pose_estimator: BasePoseEstimator | None = None,
    head_down_threshold_seconds: int,
    fall_threshold_seconds: int,
    inactivity_threshold_seconds: int,
    movement_threshold_px: float,
) -> PostureAnalyzer:
    return PostureAnalyzer(
        pose_estimator=pose_estimator,
        head_down_threshold_seconds=head_down_threshold_seconds,
        fall_threshold_seconds=fall_threshold_seconds,
        inactivity_threshold_seconds=inactivity_threshold_seconds,
        movement_threshold_px=movement_threshold_px,
    )


def _match_pose_detections(
    detections: list[Detection],
    pose_detections: list[PoseDetection],
) -> dict[int, PoseDetection]:
    assignments: dict[int, PoseDetection] = {}
    used_pose_indices: set[int] = set()
    candidates: list[tuple[float, int, int]] = []

    for detection_index, detection in enumerate(detections):
        if detection.entity_type not in MONITORED_ENTITY_TYPES:
            continue
        for pose_index, pose_detection in enumerate(pose_detections):
            overlap = _bbox_iou(detection.bbox, pose_detection.bbox)
            if overlap >= POSE_MATCH_IOU_THRESHOLD:
                candidates.append((overlap, detection_index, pose_index))

    for _, detection_index, pose_index in sorted(candidates, key=lambda item: item[0], reverse=True):
        if detection_index in assignments or pose_index in used_pose_indices:
            continue
        assignments[detection_index] = pose_detections[pose_index]
        used_pose_indices.add(pose_index)

    return assignments


def _classify_pose(detection: Detection, pose_match: PoseDetection | None) -> str | None:
    if pose_match is None:
        return None

    if _is_fallen(detection, pose_match):
        return "fallen"

    zone_type = str(detection.details.get("zone_type") or "").strip()
    if zone_type in HEAD_DOWN_ZONE_TYPES and _is_head_down(detection, pose_match):
        return "head_down"

    return None


def _is_fallen(detection: Detection, pose_match: PoseDetection) -> bool:
    width = detection.bbox.x2 - detection.bbox.x1
    height = detection.bbox.y2 - detection.bbox.y1
    if width <= 0 or height <= 0:
        return False

    shoulder_mid = _average_keypoint(pose_match, ("left_shoulder", "right_shoulder"))
    hip_mid = _average_keypoint(pose_match, ("left_hip", "right_hip"))
    ankle_mid = _average_keypoint(pose_match, ("left_ankle", "right_ankle"))

    visible_points = [point for point in (shoulder_mid, hip_mid, ankle_mid) if point is not None]
    if len(visible_points) >= 2:
        horizontal_span = max(point[0] for point in visible_points) - min(point[0] for point in visible_points)
        vertical_span = max(point[1] for point in visible_points) - min(point[1] for point in visible_points)
        if horizontal_span > vertical_span * 1.2 and width >= height * 0.95:
            return True

    if shoulder_mid is not None and hip_mid is not None:
        torso_angle = abs(degrees(atan2(hip_mid[1] - shoulder_mid[1], hip_mid[0] - shoulder_mid[0])))
        if torso_angle <= 35 and width >= height * 0.9:
            return True

    return width >= height * 1.45


def _is_head_down(detection: Detection, pose_match: PoseDetection) -> bool:
    width = detection.bbox.x2 - detection.bbox.x1
    height = detection.bbox.y2 - detection.bbox.y1
    if width <= 0 or height <= 0 or width >= height * 1.1:
        return False

    head_point = _head_point(pose_match)
    shoulder_mid = _average_keypoint(pose_match, ("left_shoulder", "right_shoulder"))
    hip_mid = _average_keypoint(pose_match, ("left_hip", "right_hip"))
    if head_point is None or shoulder_mid is None:
        return False

    torso_height = (hip_mid[1] - shoulder_mid[1]) if hip_mid is not None else (height * 0.35)
    torso_height = max(torso_height, height * 0.18)

    return head_point[1] >= shoulder_mid[1] - (torso_height * 0.05)


def _head_point(pose_match: PoseDetection) -> tuple[float, float] | None:
    for names in (
        ("nose",),
        ("left_eye", "right_eye"),
        ("left_ear", "right_ear"),
    ):
        point = _average_keypoint(pose_match, names)
        if point is not None:
            return point
    return None


def _average_keypoint(
    pose_match: PoseDetection,
    names: tuple[str, ...],
) -> tuple[float, float] | None:
    visible = [pose_match.keypoints[name] for name in names if name in pose_match.keypoints]
    if not visible:
        return None
    return (
        sum(point.x for point in visible) / len(visible),
        sum(point.y for point in visible) / len(visible),
    )


def _apply_pose_posture(
    *,
    detection: Detection,
    posture: str,
    hold_seconds: float,
    pose_match: PoseDetection | None,
) -> Detection:
    details = _clean_posture_details(detection.details)
    details.update(
        {
            "posture": posture,
            "posture_source": "pose_model",
            "posture_hold_seconds": int(max(hold_seconds, 0)),
        }
    )
    if pose_match is not None:
        details["pose_confidence"] = round(pose_match.confidence, 3)

    return detection.model_copy(update={"posture": posture, "details": details})


def _apply_inactivity_posture(detection: Detection, inactive_seconds: int) -> Detection:
    details = _clean_posture_details(detection.details)
    details.update(
        {
            "posture": "inactive",
            "inactive_seconds": inactive_seconds,
            "posture_source": "movement_watch",
        }
    )
    return detection.model_copy(update={"posture": "inactive", "details": details})


def _clear_posture_details(detection: Detection) -> Detection:
    return detection.model_copy(
        update={
            "posture": None,
            "details": _clean_posture_details(detection.details),
        }
    )


def _clean_posture_details(details: dict[str, object]) -> dict[str, object]:
    cleaned = dict(details)
    for key in (
        "posture",
        "inactive_seconds",
        "posture_source",
        "pose_confidence",
        "posture_hold_seconds",
    ):
        cleaned.pop(key, None)
    return cleaned


def _bbox_center(bbox: BoundingBox) -> tuple[float, float]:
    return ((bbox.x1 + bbox.x2) / 2, (bbox.y1 + bbox.y2) / 2)


def _center_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _bbox_iou(first: BoundingBox, second: BoundingBox) -> float:
    intersection_x1 = max(first.x1, second.x1)
    intersection_y1 = max(first.y1, second.y1)
    intersection_x2 = min(first.x2, second.x2)
    intersection_y2 = min(first.y2, second.y2)

    intersection_width = max(0.0, intersection_x2 - intersection_x1)
    intersection_height = max(0.0, intersection_y2 - intersection_y1)
    intersection_area = intersection_width * intersection_height
    if intersection_area <= 0:
        return 0.0

    first_area = max(0.0, first.x2 - first.x1) * max(0.0, first.y2 - first.y1)
    second_area = max(0.0, second.x2 - second.x1) * max(0.0, second.y2 - second.y1)
    union_area = first_area + second_area - intersection_area
    if union_area <= 0:
        return 0.0

    return intersection_area / union_area
