from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    worker_name: str = "detection-ai-worker"
    api_base_url: str = "http://localhost:8000/api/v1"
    api_internal_token: str = "internal-local-token"
    site_id: str = ""
    camera_id: str = ""
    camera_source_type: str = "webcam"
    camera_source: str = "0"
    detector_type: str = "mock"
    yolo_model: str = "yolov8n.pt"
    frame_stride: int = 5
    confidence_threshold: float = 0.55
    alert_cooldown_seconds: int = 12
    preview_output_dir: str = "../../storage/live"
    snapshot_output_dir: str = "../../storage/snapshots"
    face_model_dir: str = "../../models/opencv"
    face_profile_refresh_seconds: int = 60
    face_match_threshold: float = 0.45
    enable_pose_posture: bool = True
    pose_model: str = "yolov8n-pose.pt"
    pose_confidence_threshold: float = 0.5
    head_down_threshold_seconds: int = 8
    inactivity_threshold_seconds: int = 20
    inactivity_movement_threshold_px: float = 24.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
