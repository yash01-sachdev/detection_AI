from enum import Enum


class UserRole(str, Enum):
    admin = "admin"
    supervisor = "supervisor"
    viewer = "viewer"


class SiteType(str, Enum):
    home = "home"
    office = "office"
    restaurant = "restaurant"


class CameraSourceType(str, Enum):
    webcam = "webcam"
    droidcam = "droidcam"
    rtsp = "rtsp"
    uploaded_video = "uploaded_video"


class ZoneType(str, Enum):
    entry = "entry"
    restricted = "restricted"
    desk = "desk"
    smoking_area = "smoking_area"
    work_area = "work_area"
    general = "general"


class EntityType(str, Enum):
    person = "person"
    employee = "employee"
    dog = "dog"
    vehicle = "vehicle"
    unknown = "unknown"


class RuleSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertStatus(str, Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"

