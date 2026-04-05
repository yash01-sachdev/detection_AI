export type User = {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
}

export type Site = {
  id: string
  name: string
  site_type: string
  timezone: string
  description: string
  is_active: boolean
}

export type Camera = {
  id: string
  site_id: string
  name: string
  source_type: string
  source_value: string
  is_enabled: boolean
}

export type EmployeeFaceProfile = {
  id: string
  employee_id: string
  source_image_path: string
}

export type Employee = {
  id: string
  site_id: string | null
  employee_code: string
  first_name: string
  last_name: string
  role_title: string
  is_active: boolean
  shift_name: string
  shift_start_time: string
  shift_end_time: string
  shift_grace_minutes: number
  shift_days: string[]
  face_profiles: EmployeeFaceProfile[]
}

export type EmployeeReportSubject = {
  id: string
  employee_code: string
  full_name: string
  role_title: string
  site_id: string | null
  site_name: string | null
  timezone: string
  shift_name: string
  shift_start_time: string
  shift_end_time: string
  shift_grace_minutes: number
  shift_days: string[]
  shift_crosses_midnight: boolean
}

export type EmployeeZoneVisitStat = {
  zone_name: string
  visit_count: number
}

export type EmployeeReportTotals = {
  presence_minutes: number
  sighting_count: number
  alert_count: number
  violation_count: number
  zone_visit_count: number
  days_observed: number
  inactivity_event_count: number
  longest_inactivity_seconds: number
}

export type EmployeeAttendanceTotals = {
  scheduled_days: number
  attended_days: number
  on_time_days: number
  late_days: number
  missed_days: number
  off_day_activity_days: number
  outside_shift_sighting_count: number
}

export type EmployeeDaySummary = {
  date: string
  first_seen_at: string | null
  last_seen_at: string | null
  presence_minutes: number
  sighting_count: number
  alert_count: number
  violation_count: number
  inactivity_event_count: number
  top_zones: EmployeeZoneVisitStat[]
}

export type EmployeeTimelineItem = {
  item_type: string
  occurred_at: string
  title: string
  description: string
  zone_name: string | null
  camera_name: string | null
  severity: string | null
  status: string | null
  posture: string | null
  inactive_seconds: number | null
}

export type EmployeeAttendanceDay = {
  date: string
  is_scheduled: boolean
  status: string
  first_seen_at: string | null
  last_seen_at: string | null
  arrival_delta_minutes: number | null
  outside_shift_sighting_count: number
}

export type EmployeeReport = {
  employee: EmployeeReportSubject
  generated_at: string
  window_start: string
  window_end: string
  days: number
  totals: EmployeeReportTotals
  attendance_totals: EmployeeAttendanceTotals
  zone_visits: EmployeeZoneVisitStat[]
  daily_summaries: EmployeeDaySummary[]
  attendance_days: EmployeeAttendanceDay[]
  recent_timeline: EmployeeTimelineItem[]
}

export type ZonePoint = {
  x: number
  y: number
}

export type Zone = {
  id: string
  site_id: string
  name: string
  zone_type: string
  color: string
  is_restricted: boolean
  points: ZonePoint[]
}

export type Rule = {
  id: string
  site_id: string | null
  applies_to_site_type: string | null
  template_key: string
  name: string
  description: string
  conditions: Record<string, unknown>
  actions: Record<string, unknown>
  severity: string
  is_default: boolean
  is_enabled: boolean
}

export type Alert = {
  id: string
  site_id: string
  camera_id: string | null
  rule_id: string | null
  event_id: string | null
  title: string
  description: string
  severity: string
  status: string
  snapshot_path: string | null
  occurred_at: string
  details: Record<string, unknown>
}

export type ModeRuleTemplate = {
  template_key: string
  name: string
  description: string
  severity: string
}

export type ModeTemplate = {
  site_type: string
  label: string
  description: string
  rules: ModeRuleTemplate[]
}

export type DashboardStat = {
  key: string
  label: string
  value: number
}

export type DashboardOverview = {
  stats: DashboardStat[]
  recent_alerts: Alert[]
}

export type LiveMonitorStatus = {
  worker_name: string
  camera_source_type: string
  camera_source: string
  camera_connected: boolean
  frame_updated_at: string | null
  frame_count: number
  last_detection_count: number
  last_labels: string[]
  message: string
  frame_url: string | null
}
