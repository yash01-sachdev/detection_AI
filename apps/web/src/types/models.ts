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

