from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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


def ingest_detection_event(db: Session, payload: DetectionIngestRequest) -> DetectionIngestResponse:
    occurred_at = payload.occurred_at or datetime.now(UTC)
    event = Event(
        site_id=payload.site_id,
        camera_id=payload.camera_id,
        zone_id=payload.zone_id,
        entity_type=payload.entity_type,
        label=payload.label,
        track_id=payload.track_id,
        confidence=payload.confidence,
        occurred_at=occurred_at,
        details=payload.details,
    )
    db.add(event)
    db.flush()

    alert_id: str | None = None
    if payload.alert_title:
        alert = Alert(
            site_id=payload.site_id,
            camera_id=payload.camera_id,
            rule_id=payload.rule_id,
            event_id=event.id,
            title=payload.alert_title,
            description=payload.alert_description or "",
            severity=payload.severity,
            status=AlertStatus.open,
            snapshot_path=payload.snapshot_path,
            occurred_at=occurred_at,
            details=payload.details,
        )
        db.add(alert)
        db.flush()
        alert_id = alert.id

    db.commit()
    return DetectionIngestResponse(event_id=event.id, alert_id=alert_id)

