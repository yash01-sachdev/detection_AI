from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.alert import Alert
from app.models.camera import Camera
from app.models.enums import AlertStatus, RuleSeverity, SiteType
from app.models.event import Event
from app.models.rule import Rule
from app.models.site import Site
from app.models.zone import Zone
from app.schemas.monitoring import (
    DashboardOverview,
    DashboardStat,
    DetectionIngestRequest,
    DetectionIngestResponse,
    ModeRuleTemplate,
    ModeTemplate,
    SiteCreate,
)

MODE_RULES: dict[SiteType, dict[str, object]] = {
    SiteType.home: {
        "label": "Home",
        "description": "Detect people, animals, and suspicious movement around gates, entrances, and yards.",
        "rules": [
            {
                "template_key": "home_unknown_at_gate",
                "name": "Unknown Person At Gate",
                "description": "Alert when a person appears inside the gate or entry zone.",
                "severity": RuleSeverity.high,
                "conditions": {"entity_type": "person", "zone_type": "entry"},
                "actions": {"create_alert": True, "snapshot": True},
            },
            {
                "template_key": "home_dog_entry",
                "name": "Dog Detected In Entry Zone",
                "description": "Alert when a dog appears in the monitored home entry zone.",
                "severity": RuleSeverity.medium,
                "conditions": {"entity_type": "dog", "zone_type": "entry"},
                "actions": {"create_alert": True, "snapshot": True},
            },
        ],
    },
    SiteType.office: {
        "label": "Office",
        "description": "Track workplace safety, restricted areas, desk inactivity, and employee presence.",
        "rules": [
            {
                "template_key": "office_restricted_zone",
                "name": "Restricted Zone Entry",
                "description": "Alert when anyone enters a restricted zone.",
                "severity": RuleSeverity.high,
                "conditions": {"entity_type": "person", "zone_type": "restricted"},
                "actions": {"create_alert": True, "snapshot": True},
            },
            {
                "template_key": "office_desk_inactivity",
                "name": "Desk Inactivity Watch",
                "description": "Track inactivity in desk zones for later workflow analysis.",
                "severity": RuleSeverity.medium,
                "conditions": {"entity_type": "person", "zone_type": "desk", "posture": "inactive"},
                "actions": {"create_alert": False, "record_metric": True},
            },
            {
                "template_key": "office_head_down_watch",
                "name": "Head-Down Desk Alert",
                "description": "Alert when a person stays in a head-down posture at a desk.",
                "severity": RuleSeverity.medium,
                "conditions": {"entity_type": "person", "zone_type": "desk", "posture": "head_down"},
                "actions": {"create_alert": True, "snapshot": True},
            },
            {
                "template_key": "office_fall_detection",
                "name": "Fall Detection",
                "description": "Alert when a person shows a fall-like posture anywhere in the office.",
                "severity": RuleSeverity.critical,
                "conditions": {"entity_type": "person", "posture": "fallen"},
                "actions": {"create_alert": True, "snapshot": True},
            },
        ],
    },
    SiteType.restaurant: {
        "label": "Restaurant",
        "description": "Monitor staff movement, restricted areas, and policy violations in operational zones.",
        "rules": [
            {
                "template_key": "restaurant_smoking_area",
                "name": "Employee In Smoking Area",
                "description": "Alert when an employee enters the restricted smoking area.",
                "severity": RuleSeverity.high,
                "conditions": {"entity_type": "employee", "zone_type": "smoking_area"},
                "actions": {"create_alert": True, "snapshot": True},
            },
            {
                "template_key": "restaurant_storage_access",
                "name": "Unauthorized Storage Access",
                "description": "Alert when someone enters the restricted storage zone.",
                "severity": RuleSeverity.high,
                "conditions": {"entity_type": "person", "zone_type": "restricted"},
                "actions": {"create_alert": True, "snapshot": True},
            },
        ],
    },
}


def list_mode_templates() -> list[ModeTemplate]:
    templates: list[ModeTemplate] = []
    for site_type, config in MODE_RULES.items():
        templates.append(
            ModeTemplate(
                site_type=site_type.value,
                label=config["label"],
                description=config["description"],
                rules=[
                    ModeRuleTemplate(
                        template_key=rule["template_key"],
                        name=rule["name"],
                        description=rule["description"],
                        severity=rule["severity"].value,
                    )
                    for rule in config["rules"]
                ],
            )
        )
    return templates


def create_site_with_default_rules(db: Session, payload: SiteCreate) -> Site:
    site = Site(
        name=payload.name,
        site_type=payload.site_type,
        timezone=payload.timezone,
        description=payload.description,
    )
    db.add(site)
    db.flush()

    for rule in MODE_RULES[site.site_type]["rules"]:
        db.add(
            Rule(
                site_id=site.id,
                applies_to_site_type=site.site_type,
                template_key=rule["template_key"],
                name=rule["name"],
                description=rule["description"],
                conditions=rule["conditions"],
                actions=rule["actions"],
                severity=rule["severity"],
                is_default=True,
                is_enabled=True,
            )
        )

    db.commit()
    db.refresh(site)
    return site


def build_dashboard_overview(db: Session) -> DashboardOverview:
    stats = [
        DashboardStat(key="sites", label="Sites", value=db.scalar(select(func.count(Site.id))) or 0),
        DashboardStat(key="cameras", label="Cameras", value=db.scalar(select(func.count(Camera.id))) or 0),
        DashboardStat(key="zones", label="Zones", value=db.scalar(select(func.count(Zone.id))) or 0),
        DashboardStat(key="rules", label="Rules", value=db.scalar(select(func.count(Rule.id))) or 0),
        DashboardStat(key="alerts", label="Alerts", value=db.scalar(select(func.count(Alert.id))) or 0),
    ]
    recent_alerts = list(db.scalars(select(Alert).order_by(Alert.occurred_at.desc()).limit(8)))
    return DashboardOverview(stats=stats, recent_alerts=recent_alerts)


def list_site_zones(db: Session, site_id: str) -> list[Zone]:
    return list(
        db.scalars(
            select(Zone)
            .where(Zone.site_id == site_id)
            .order_by(Zone.created_at.asc())
        )
    )


def ingest_detection_event(db: Session, payload: DetectionIngestRequest) -> DetectionIngestResponse:
    occurred_at = payload.occurred_at or datetime.now(UTC)
    zone = db.get(Zone, payload.zone_id) if payload.zone_id else None
    details = dict(payload.details)
    details.setdefault("track_id", payload.track_id)
    details.setdefault("entity_type", _normalize_value(payload.entity_type))
    details.setdefault("zone_id", payload.zone_id)
    details.setdefault("subject_label", payload.label)
    if zone is not None:
        details.setdefault("zone_name", zone.name)
        details.setdefault("zone_type", zone.zone_type.value)
        details.setdefault("zone_restricted", zone.is_restricted)

    event = Event(
        site_id=payload.site_id,
        camera_id=payload.camera_id,
        zone_id=payload.zone_id,
        entity_type=payload.entity_type,
        label=payload.label,
        track_id=payload.track_id,
        confidence=payload.confidence,
        occurred_at=occurred_at,
        details=details,
    )
    db.add(event)
    db.flush()

    matched_rule = _find_matching_rule(db, payload.site_id, payload, zone, details)
    alert_data = _build_alert_data(
        payload=payload,
        zone=zone,
        details=details,
        matched_rule=matched_rule,
    )

    alert_id: str | None = None
    if alert_data is not None:
        duplicate_alert = _find_recent_duplicate_alert(
            db=db,
            payload=payload,
            alert_data=alert_data,
            details=details,
            occurred_at=occurred_at,
        )

        if duplicate_alert is not None:
            _merge_duplicate_alert(
                alert=duplicate_alert,
                event=event,
                payload=payload,
                details=details,
                occurred_at=occurred_at,
            )
            alert_id = duplicate_alert.id
        else:
            alert = Alert(
                site_id=payload.site_id,
                camera_id=payload.camera_id,
                rule_id=alert_data["rule_id"],
                event_id=event.id,
                title=alert_data["title"],
                description=alert_data["description"],
                severity=alert_data["severity"],
                status=AlertStatus.open,
                snapshot_path=payload.snapshot_path,
                occurred_at=occurred_at,
                details=_build_alert_details(details, alert_data, occurred_at),
            )
            db.add(alert)
            db.flush()
            alert_id = alert.id

    db.commit()
    return DetectionIngestResponse(event_id=event.id, alert_id=alert_id)


def _find_matching_rule(
    db: Session,
    site_id: str,
    payload: DetectionIngestRequest,
    zone: Zone | None,
    details: dict[str, object],
) -> Rule | None:
    rules = list(
        db.scalars(
            select(Rule)
            .where(Rule.site_id == site_id, Rule.is_enabled.is_(True))
            .order_by(Rule.is_default.asc(), Rule.created_at.asc())
        )
    )

    for rule in rules:
        if _rule_matches(rule, payload, zone, details):
            return rule

    return None


def _find_recent_duplicate_alert(
    *,
    db: Session,
    payload: DetectionIngestRequest,
    alert_data: dict[str, Any],
    details: dict[str, object],
    occurred_at: datetime,
) -> Alert | None:
    settings = get_settings()
    cutoff = occurred_at - timedelta(seconds=max(settings.alert_dedup_seconds, 1))

    recent_alerts = list(
        db.scalars(
            select(Alert)
            .where(
                Alert.site_id == payload.site_id,
                Alert.camera_id == payload.camera_id,
                Alert.status == AlertStatus.open,
                Alert.occurred_at >= cutoff,
            )
            .order_by(Alert.occurred_at.desc())
            .limit(20)
        )
    )

    current_subject_key = _build_alert_subject_key(payload, details)
    for alert in recent_alerts:
        alert_details = dict(alert.details or {})
        if alert_data["rule_id"] is not None:
            if alert.rule_id != alert_data["rule_id"]:
                continue
        elif alert.title != alert_data["title"]:
            continue
        if str(alert_details.get("zone_id") or "") != str(payload.zone_id or ""):
            continue
        if str(alert_details.get("subject_key") or "") != current_subject_key:
            continue
        return alert

    return None


def _merge_duplicate_alert(
    *,
    alert: Alert,
    event: Event,
    payload: DetectionIngestRequest,
    details: dict[str, object],
    occurred_at: datetime,
) -> None:
    alert_details = dict(alert.details or {})
    previous_occurred_at = alert.occurred_at
    repeat_count = int(alert_details.get("repeat_count", 1)) + 1

    alert.event_id = event.id
    alert.snapshot_path = payload.snapshot_path or alert.snapshot_path
    alert.occurred_at = occurred_at
    alert_details.update(details)
    alert_details["repeat_count"] = repeat_count
    alert_details.setdefault("first_seen_at", previous_occurred_at.isoformat())
    alert_details["last_seen_at"] = occurred_at.isoformat()
    alert_details["last_confidence"] = payload.confidence
    alert.details = alert_details


def _build_alert_details(
    details: dict[str, object],
    alert_data: dict[str, Any],
    occurred_at: datetime,
) -> dict[str, object]:
    alert_details = dict(details)
    alert_details["subject_key"] = _build_alert_subject_key_from_details(alert_details)
    alert_details["repeat_count"] = 1
    alert_details["first_seen_at"] = occurred_at.isoformat()
    alert_details["last_seen_at"] = occurred_at.isoformat()
    alert_details["rule_name"] = alert_data["title"]
    return alert_details


def _rule_matches(
    rule: Rule,
    payload: DetectionIngestRequest,
    zone: Zone | None,
    details: dict[str, object],
) -> bool:
    zone_type = zone.zone_type.value if zone is not None else None
    actual_values = {
        "entity_type": _normalize_value(payload.entity_type),
        "zone_id": zone.id if zone is not None else None,
        "zone_type": zone_type,
        "posture": details.get("posture"),
        "label": payload.label,
        "zone_restricted": zone.is_restricted if zone is not None else None,
    }

    for key, expected in rule.conditions.items():
        actual = actual_values.get(key)
        if not _condition_matches(key, actual, expected):
            return False

    return True


def _build_alert_data(
    *,
    payload: DetectionIngestRequest,
    zone: Zone | None,
    details: dict[str, object],
    matched_rule: Rule | None,
) -> dict[str, Any] | None:
    if matched_rule is not None:
        if matched_rule.actions.get("create_alert"):
            return {
                "title": matched_rule.name,
                "description": _build_rule_alert_description(matched_rule, payload, zone),
                "severity": matched_rule.severity,
                "rule_id": matched_rule.id,
            }
        return None

    if payload.alert_title:
        return {
            "title": payload.alert_title,
            "description": payload.alert_description
            or _build_generic_alert_description(payload, zone, details),
            "severity": payload.severity,
            "rule_id": payload.rule_id,
        }

    return None


def _build_rule_alert_description(
    rule: Rule,
    payload: DetectionIngestRequest,
    zone: Zone | None,
) -> str:
    subject = payload.label.replace("_", " ").title()
    confidence_pct = round(payload.confidence * 100)
    if zone is not None:
        return (
            f"{subject} matched rule {rule.name} in zone {zone.name} "
            f"({zone.zone_type.value}) with {confidence_pct}% confidence."
        )
    return f"{subject} matched rule {rule.name} with {confidence_pct}% confidence."


def _build_generic_alert_description(
    payload: DetectionIngestRequest,
    zone: Zone | None,
    details: dict[str, object],
) -> str:
    subject = payload.label.replace("_", " ")
    confidence_pct = round(payload.confidence * 100)
    if zone is not None:
        return (
            f"Live worker detected {subject} in zone {zone.name} "
            f"({zone.zone_type.value}) with {confidence_pct}% confidence."
        )
    return (
        f"Live worker detected {subject} on camera {payload.camera_id} "
        f"with {confidence_pct}% confidence."
    )


def _normalize_value(value: object) -> object:
    if hasattr(value, "value"):
        return getattr(value, "value")
    return value


def _build_alert_subject_key(payload: DetectionIngestRequest, details: dict[str, object]) -> str:
    employee_id = str(details.get("employee_id") or "").strip()
    if employee_id:
        return f"employee:{employee_id}"

    track_id = str(payload.track_id or "").strip()
    if track_id:
        return f"track:{track_id}"

    identity = str(details.get("identity") or "").strip()
    if identity:
        return f"identity:{identity.lower()}"

    return f"label:{payload.label.lower()}"


def _build_alert_subject_key_from_details(details: dict[str, object]) -> str:
    employee_id = str(details.get("employee_id") or "").strip()
    if employee_id:
        return f"employee:{employee_id}"

    track_id = str(details.get("track_id") or "").strip()
    if track_id:
        return f"track:{track_id}"

    identity = str(details.get("identity") or "").strip()
    if identity:
        return f"identity:{identity.lower()}"

    return f"label:{str(details.get('subject_label') or '').lower()}"


def _condition_matches(key: str, actual: object, expected: object) -> bool:
    if isinstance(expected, list):
        return any(_condition_matches(key, actual, item) for item in expected)

    if key == "entity_type":
        return _entity_type_matches(actual, expected)

    return _normalize_value(actual) == _normalize_value(expected)


def _entity_type_matches(actual: object, expected: object) -> bool:
    actual_value = _normalize_value(actual)
    expected_value = _normalize_value(expected)

    if actual_value == expected_value:
        return True

    # An employee is still a person for generic person-scoped rules.
    if expected_value == "person" and actual_value == "employee":
        return True

    return False
