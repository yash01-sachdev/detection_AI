from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, Camera, Employee, Event, Site
from app.schemas.monitoring import (
    EmployeeAttendanceDay,
    EmployeeAttendanceTotals,
    EmployeeDaySummary,
    EmployeeReportRead,
    EmployeeReportSubject,
    EmployeeReportTotals,
    EmployeeTimelineItem,
    EmployeeZoneVisitStat,
)

SESSION_GAP_MINUTES = 15
MIN_SESSION_MINUTES = 1
MAX_REPORT_DAYS = 90
MAX_TIMELINE_ITEMS = 40
DEFAULT_SHIFT_DAYS = ["mon", "tue", "wed", "thu", "fri"]
WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass
class SessionWindow:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class ShiftSchedule:
    name: str
    start_text: str
    end_text: str
    grace_minutes: int
    days: list[str]
    start_time: time
    end_time: time
    crosses_midnight: bool


def build_employee_report(db: Session, employee_id: str, days: int) -> EmployeeReportRead:
    return build_employee_report_at(db, employee_id, days)


def build_employee_report_at(
    db: Session,
    employee_id: str,
    days: int,
    reference_time: datetime | None = None,
) -> EmployeeReportRead:
    clamped_days = min(max(days, 1), MAX_REPORT_DAYS)
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    site = db.get(Site, employee.site_id) if employee.site_id else None
    timezone_name = site.timezone if site is not None else "UTC"
    timezone = ZoneInfo(timezone_name)
    window_end = reference_time or datetime.now(UTC)
    window_start = window_end - timedelta(days=clamped_days)

    schedule = _build_shift_schedule(employee)
    cameras = _load_cameras_by_id(db, employee.site_id)
    events = _load_employee_events(db, employee, window_start, window_end)
    alerts = _load_employee_alerts(db, employee, window_start, window_end)

    zone_visits = _build_zone_visits(events)
    day_summaries = _build_day_summaries(events, alerts, timezone)
    attendance_totals, attendance_days = _build_attendance_days(
        events,
        schedule,
        timezone,
        window_start,
        window_end,
    )
    timeline = _build_recent_timeline(events, alerts, cameras, timezone)

    return EmployeeReportRead(
        employee=EmployeeReportSubject(
            id=employee.id,
            employee_code=employee.employee_code,
            full_name=f"{employee.first_name} {employee.last_name}".strip(),
            role_title=employee.role_title,
            site_id=employee.site_id,
            site_name=site.name if site is not None else None,
            timezone=timezone_name,
            shift_name=schedule.name,
            shift_start_time=schedule.start_text,
            shift_end_time=schedule.end_text,
            shift_grace_minutes=schedule.grace_minutes,
            shift_days=schedule.days,
            shift_crosses_midnight=schedule.crosses_midnight,
        ),
        generated_at=window_end,
        window_start=window_start,
        window_end=window_end,
        days=clamped_days,
        totals=EmployeeReportTotals(
            presence_minutes=sum(day.presence_minutes for day in day_summaries),
            sighting_count=len(events),
            alert_count=len(alerts),
            violation_count=sum(1 for alert in alerts if _is_violation_alert(alert)),
            zone_visit_count=sum(zone.visit_count for zone in zone_visits),
            days_observed=sum(1 for day in day_summaries if day.sighting_count > 0),
            inactivity_event_count=sum(1 for event in events if _event_is_inactive(event)),
            longest_inactivity_seconds=max((_event_inactive_seconds(event) for event in events), default=0),
        ),
        attendance_totals=attendance_totals,
        zone_visits=zone_visits,
        daily_summaries=day_summaries,
        attendance_days=attendance_days,
        recent_timeline=timeline,
    )


def _build_shift_schedule(employee: Employee) -> ShiftSchedule:
    start_text = _normalize_shift_time(employee.shift_start_time, "09:00")
    end_text = _normalize_shift_time(employee.shift_end_time, "17:00")
    start_time = datetime.strptime(start_text, "%H:%M").time()
    end_time = datetime.strptime(end_text, "%H:%M").time()
    days = [day for day in (employee.shift_days or DEFAULT_SHIFT_DAYS) if day in WEEKDAY_KEYS] or list(DEFAULT_SHIFT_DAYS)

    return ShiftSchedule(
        name=(employee.shift_name or "Day Shift").strip() or "Day Shift",
        start_text=start_text,
        end_text=end_text,
        grace_minutes=max(int(employee.shift_grace_minutes or 0), 0),
        days=days,
        start_time=start_time,
        end_time=end_time,
        crosses_midnight=end_time <= start_time,
    )


def _load_cameras_by_id(db: Session, site_id: str | None) -> dict[str, Camera]:
    statement = select(Camera)
    if site_id:
        statement = statement.where(Camera.site_id == site_id)
    return {camera.id: camera for camera in db.scalars(statement)}


def _load_employee_events(
    db: Session,
    employee: Employee,
    window_start: datetime,
    window_end: datetime,
) -> list[Event]:
    statement = select(Event).where(
        Event.occurred_at >= window_start,
        Event.occurred_at <= window_end,
    )
    if employee.site_id:
        statement = statement.where(Event.site_id == employee.site_id)

    events = list(db.scalars(statement.order_by(Event.occurred_at.asc())))
    return [
        event
        for event in events
        if str((event.details or {}).get("employee_id") or "") == employee.id
    ]


def _load_employee_alerts(
    db: Session,
    employee: Employee,
    window_start: datetime,
    window_end: datetime,
) -> list[Alert]:
    statement = select(Alert).where(
        Alert.occurred_at >= window_start,
        Alert.occurred_at <= window_end,
    )
    if employee.site_id:
        statement = statement.where(Alert.site_id == employee.site_id)

    alerts = list(db.scalars(statement.order_by(Alert.occurred_at.desc())))
    return [
        alert
        for alert in alerts
        if str((alert.details or {}).get("employee_id") or "") == employee.id
    ]


def _build_zone_visits(events: list[Event]) -> list[EmployeeZoneVisitStat]:
    zone_counter: Counter[str] = Counter()
    previous_zone_key = ""

    for event in events:
        details = dict(event.details or {})
        zone_name = str(details.get("zone_name") or "").strip()
        zone_id = str(details.get("zone_id") or event.zone_id or "").strip()
        zone_key = f"{zone_id}:{zone_name}"

        if not zone_name or zone_key == previous_zone_key:
            continue

        zone_counter[zone_name] += 1
        previous_zone_key = zone_key

    return [
        EmployeeZoneVisitStat(zone_name=zone_name, visit_count=visit_count)
        for zone_name, visit_count in zone_counter.most_common(8)
    ]


def _build_day_summaries(
    events: list[Event],
    alerts: list[Alert],
    timezone: ZoneInfo,
) -> list[EmployeeDaySummary]:
    events_by_day: dict[str, list[Event]] = defaultdict(list)
    alerts_by_day: dict[str, list[Alert]] = defaultdict(list)

    for event in events:
        events_by_day[_local_day_key(event.occurred_at, timezone)].append(event)

    for alert in alerts:
        alerts_by_day[_local_day_key(alert.occurred_at, timezone)].append(alert)

    all_days = sorted(set(events_by_day.keys()) | set(alerts_by_day.keys()), reverse=True)
    day_summaries: list[EmployeeDaySummary] = []

    for day_key in all_days:
        day_events = sorted(events_by_day.get(day_key, []), key=lambda item: item.occurred_at)
        day_alerts = alerts_by_day.get(day_key, [])
        sessions = _build_presence_sessions(day_events)
        zone_visits = _build_zone_visits(day_events)

        first_seen = day_events[0].occurred_at if day_events else None
        last_seen = day_events[-1].occurred_at if day_events else None
        presence_minutes = sum(
            max(int((session.end - session.start).total_seconds() // 60), MIN_SESSION_MINUTES)
            for session in sessions
        )

        day_summaries.append(
            EmployeeDaySummary(
                date=day_key,
                first_seen_at=first_seen,
                last_seen_at=last_seen,
                presence_minutes=presence_minutes,
                sighting_count=len(day_events),
                alert_count=len(day_alerts),
                violation_count=sum(1 for alert in day_alerts if _is_violation_alert(alert)),
                inactivity_event_count=sum(1 for event in day_events if _event_is_inactive(event)),
                top_zones=zone_visits[:3],
            )
        )

    return day_summaries


def _build_attendance_days(
    events: list[Event],
    schedule: ShiftSchedule,
    timezone: ZoneInfo,
    window_start: datetime,
    window_end: datetime,
) -> tuple[EmployeeAttendanceTotals, list[EmployeeAttendanceDay]]:
    events_by_attendance_day: dict[str, list[tuple[Event, datetime]]] = defaultdict(list)
    for event in events:
        local_time = _as_local_time(event.occurred_at, timezone)
        attendance_day = _attendance_day_key(local_time, schedule)
        events_by_attendance_day[attendance_day].append((event, local_time))

    local_start_day = window_start.astimezone(timezone).date()
    local_end_day = window_end.astimezone(timezone).date()
    attendance_days: list[EmployeeAttendanceDay] = []

    current_day = local_end_day
    while current_day >= local_start_day:
        day_key = current_day.isoformat()
        is_scheduled = _weekday_key(current_day) in schedule.days
        day_events = sorted(events_by_attendance_day.get(day_key, []), key=lambda item: item[1])

        if not is_scheduled and not day_events:
            current_day -= timedelta(days=1)
            continue

        if is_scheduled:
            attendance_days.append(
                _build_scheduled_attendance_day(
                    current_day=current_day,
                    day_events=day_events,
                    schedule=schedule,
                    timezone=timezone,
                )
            )
        else:
            attendance_days.append(_build_off_day_activity(day_key, day_events))

        current_day -= timedelta(days=1)

    totals = EmployeeAttendanceTotals(
        scheduled_days=sum(1 for day in attendance_days if day.is_scheduled),
        attended_days=sum(1 for day in attendance_days if day.status in {"on_time", "late"}),
        on_time_days=sum(1 for day in attendance_days if day.status == "on_time"),
        late_days=sum(1 for day in attendance_days if day.status == "late"),
        missed_days=sum(1 for day in attendance_days if day.status == "missed"),
        off_day_activity_days=sum(1 for day in attendance_days if day.status == "off_day_activity"),
        outside_shift_sighting_count=sum(day.outside_shift_sighting_count for day in attendance_days),
    )
    return totals, attendance_days


def _build_scheduled_attendance_day(
    *,
    current_day: date,
    day_events: list[tuple[Event, datetime]],
    schedule: ShiftSchedule,
    timezone: ZoneInfo,
) -> EmployeeAttendanceDay:
    shift_start, shift_end = _shift_window_for_day(current_day, schedule, timezone)
    grace_cutoff = shift_start + timedelta(minutes=schedule.grace_minutes)

    if not day_events:
        return EmployeeAttendanceDay(
            date=current_day.isoformat(),
            is_scheduled=True,
            status="missed",
        )

    first_seen = day_events[0][1]
    last_seen = day_events[-1][1]
    outside_shift_sightings = sum(
        1
        for _, local_time in day_events
        if local_time < shift_start or local_time > shift_end
    )
    arrival_delta_minutes = int((first_seen - shift_start).total_seconds() // 60)

    return EmployeeAttendanceDay(
        date=current_day.isoformat(),
        is_scheduled=True,
        status="on_time" if first_seen <= grace_cutoff else "late",
        first_seen_at=first_seen,
        last_seen_at=last_seen,
        arrival_delta_minutes=arrival_delta_minutes,
        outside_shift_sighting_count=outside_shift_sightings,
    )


def _build_off_day_activity(
    day_key: str,
    day_events: list[tuple[Event, datetime]],
) -> EmployeeAttendanceDay:
    first_seen = day_events[0][1] if day_events else None
    last_seen = day_events[-1][1] if day_events else None
    return EmployeeAttendanceDay(
        date=day_key,
        is_scheduled=False,
        status="off_day_activity",
        first_seen_at=first_seen,
        last_seen_at=last_seen,
        outside_shift_sighting_count=len(day_events),
    )


def _build_presence_sessions(events: list[Event]) -> list[SessionWindow]:
    if not events:
        return []

    max_gap = timedelta(minutes=SESSION_GAP_MINUTES)
    sessions: list[SessionWindow] = []
    current_start = events[0].occurred_at
    current_end = events[0].occurred_at

    for event in events[1:]:
        if event.occurred_at - current_end <= max_gap:
            current_end = event.occurred_at
            continue

        sessions.append(SessionWindow(start=current_start, end=current_end))
        current_start = event.occurred_at
        current_end = event.occurred_at

    sessions.append(SessionWindow(start=current_start, end=current_end))
    return sessions


def _build_recent_timeline(
    events: list[Event],
    alerts: list[Alert],
    cameras: dict[str, Camera],
    timezone: ZoneInfo,
) -> list[EmployeeTimelineItem]:
    timeline_items: list[EmployeeTimelineItem] = []

    for alert in alerts:
        details = dict(alert.details or {})
        posture = _normalize_posture(details.get("posture"))
        inactive_seconds = _coerce_int(details.get("inactive_seconds"))
        timeline_items.append(
            EmployeeTimelineItem(
                item_type="alert",
                occurred_at=_as_local_time(alert.occurred_at, timezone),
                title=alert.title,
                description=_build_timeline_description(
                    zone_name=str(details.get("zone_name") or "").strip(),
                    posture=posture,
                    inactive_seconds=inactive_seconds,
                    fallback=alert.description or "Alert created.",
                ),
                zone_name=str(details.get("zone_name") or "").strip() or None,
                camera_name=cameras.get(alert.camera_id).name if alert.camera_id in cameras else None,
                severity=alert.severity.value,
                status=alert.status.value,
                posture=posture,
                inactive_seconds=inactive_seconds,
            )
        )

    for event in events:
        details = dict(event.details or {})
        subject = str(details.get("employee_code") or details.get("identity") or event.label).strip()
        zone_name = str(details.get("zone_name") or "").strip()
        posture = _normalize_posture(details.get("posture"))
        inactive_seconds = _coerce_int(details.get("inactive_seconds"))
        timeline_items.append(
            EmployeeTimelineItem(
                item_type="event",
                occurred_at=_as_local_time(event.occurred_at, timezone),
                title=_build_event_title(subject, posture),
                description=_build_timeline_description(
                    zone_name=zone_name,
                    posture=posture,
                    inactive_seconds=inactive_seconds,
                    fallback=(
                        f"Seen in {zone_name}."
                        if zone_name
                        else "Seen by the monitoring worker."
                    ),
                ),
                zone_name=zone_name or None,
                camera_name=cameras.get(event.camera_id).name if event.camera_id in cameras else None,
                posture=posture,
                inactive_seconds=inactive_seconds,
            )
        )

    timeline_items.sort(key=lambda item: item.occurred_at, reverse=True)
    return timeline_items[:MAX_TIMELINE_ITEMS]


def _shift_window_for_day(day: date, schedule: ShiftSchedule, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    shift_start = datetime.combine(day, schedule.start_time, tzinfo=timezone)
    shift_end = datetime.combine(day, schedule.end_time, tzinfo=timezone)
    if schedule.crosses_midnight:
        shift_end += timedelta(days=1)
    return shift_start, shift_end


def _attendance_day_key(local_time: datetime, schedule: ShiftSchedule) -> str:
    attendance_day = local_time.date()
    if schedule.crosses_midnight and local_time.timetz().replace(tzinfo=None) < schedule.end_time:
        attendance_day -= timedelta(days=1)
    return attendance_day.isoformat()


def _is_violation_alert(alert: Alert) -> bool:
    details = dict(alert.details or {})
    if bool(details.get("zone_restricted")):
        return True
    return alert.severity.value in {"high", "critical"}


def _local_day_key(value: datetime, timezone: ZoneInfo) -> str:
    return _as_local_time(value, timezone).date().isoformat()


def _weekday_key(value: date) -> str:
    return WEEKDAY_KEYS[value.weekday()]


def _event_is_inactive(event: Event) -> bool:
    details = dict(event.details or {})
    return _normalize_posture(details.get("posture")) == "inactive"


def _event_inactive_seconds(event: Event) -> int:
    details = dict(event.details or {})
    return _coerce_int(details.get("inactive_seconds"))


def _build_event_title(subject: str, posture: str | None) -> str:
    if posture == "inactive":
        return f"{subject} marked inactive"
    if posture == "head_down":
        return f"{subject} marked head-down"
    return f"{subject} detected"


def _build_timeline_description(
    *,
    zone_name: str,
    posture: str | None,
    inactive_seconds: int,
    fallback: str,
) -> str:
    if posture == "inactive":
        zone_label = zone_name or "the monitored area"
        if inactive_seconds > 0:
            return f"No meaningful movement for {inactive_seconds} seconds in {zone_label}."
        return f"No meaningful movement detected in {zone_label}."
    if posture == "head_down":
        zone_label = zone_name or "the monitored area"
        return f"Head-down posture detected in {zone_label}."
    return fallback


def _normalize_posture(value: object) -> str | None:
    posture = str(value or "").strip().lower()
    return posture or None


def _normalize_shift_time(value: object, fallback: str) -> str:
    text = str(value or fallback).strip()
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        return fallback
    return text


def _coerce_int(value: object) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _as_local_time(value: datetime, timezone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(timezone)
