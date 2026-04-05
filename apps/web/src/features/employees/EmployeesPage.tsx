import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { API_BASE_URL, apiRequest } from '../../lib/api/client'
import type {
  Employee,
  EmployeeDaySummary,
  EmployeeFaceProfile,
  EmployeeReport,
  EmployeeTimelineItem,
  EmployeeZoneVisitStat,
  Site,
} from '../../types/models'

const API_ROOT = API_BASE_URL.replace(/\/api\/v1\/?$/, '')

const initialEmployeeForm = {
  site_id: '',
  employee_code: '',
  first_name: '',
  last_name: '',
  role_title: '',
  is_active: true,
}

function formatDateTime(value: string | null) {
  if (!value) {
    return 'Not observed yet'
  }

  return new Date(value).toLocaleString()
}

function formatMinutes(minutes: number) {
  if (minutes < 60) {
    return `${minutes} min`
  }

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  if (!remainingMinutes) {
    return `${hours} hr`
  }
  return `${hours} hr ${remainingMinutes} min`
}

function renderZoneVisits(zoneVisits: EmployeeZoneVisitStat[]) {
  if (!zoneVisits.length) {
    return 'No zone visits yet'
  }

  return zoneVisits.map((zone) => `${zone.zone_name} (${zone.visit_count})`).join(', ')
}

function renderTimelineMeta(item: EmployeeTimelineItem) {
  const parts = [item.zone_name, item.camera_name, item.severity].filter(Boolean)
  return parts.length ? parts.join(' | ') : 'Recorded by the monitoring system'
}

function renderDaySummary(day: EmployeeDaySummary) {
  return (
    <article key={day.date} className="list-row list-row--top">
      <div>
        <strong>{day.date}</strong>
        <p>
          Presence: {formatMinutes(day.presence_minutes)} | Sightings: {day.sighting_count} | Alerts: {day.alert_count}
        </p>
        <small>
          First seen: {formatDateTime(day.first_seen_at)} | Last seen: {formatDateTime(day.last_seen_at)}
        </small>
        <small>Top zones: {renderZoneVisits(day.top_zones)}</small>
      </div>
      <div className="stack-sm align-end">
        <span className="pill pill--medium">{day.violation_count} violations</span>
      </div>
    </article>
  )
}

export function EmployeesPage() {
  const [sites, setSites] = useState<Site[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [employeeForm, setEmployeeForm] = useState(initialEmployeeForm)
  const [selectedEmployeeId, setSelectedEmployeeId] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [reportDays, setReportDays] = useState(7)
  const [report, setReport] = useState<EmployeeReport | null>(null)
  const [error, setError] = useState('')
  const [uploadMessage, setUploadMessage] = useState('')

  useEffect(() => {
    Promise.all([apiRequest<Site[]>('/sites'), apiRequest<Employee[]>('/employees')])
      .then(([loadedSites, loadedEmployees]) => {
        setSites(loadedSites)
        setEmployees(loadedEmployees)
        if (loadedSites.length) {
          setEmployeeForm((current) => ({ ...current, site_id: current.site_id || loadedSites[0].id }))
        }
        if (loadedEmployees.length) {
          setSelectedEmployeeId(loadedEmployees[0].id)
        }
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load employees.')
      })
  }, [])

  useEffect(() => {
    if (!selectedEmployeeId) {
      return
    }

    let isMounted = true

    apiRequest<EmployeeReport>(`/employees/${selectedEmployeeId}/report?days=${reportDays}`)
      .then((nextReport) => {
        if (!isMounted) {
          return
        }
        setReport(nextReport)
      })
      .catch((loadError) => {
        if (!isMounted) {
          return
        }
        setError(loadError instanceof Error ? loadError.message : 'Unable to load employee report.')
      })

    return () => {
      isMounted = false
    }
  }, [selectedEmployeeId, reportDays])

  const employeeOptions = useMemo(
    () =>
      employees.map((employee) => ({
        id: employee.id,
        label: `${employee.first_name} ${employee.last_name} (${employee.employee_code})`,
      })),
    [employees],
  )

  function selectEmployee(employeeId: string) {
    setSelectedEmployeeId(employeeId)
    setReport(null)
    setUploadMessage('')
  }

  function selectReportDays(days: number) {
    setReportDays(days)
    setReport(null)
  }

  async function handleEmployeeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    try {
      const createdEmployee = await apiRequest<Employee>('/employees', {
        method: 'POST',
        body: JSON.stringify(employeeForm),
      })
      setEmployees((current) => [createdEmployee, ...current])
      selectEmployee(createdEmployee.id)
      setEmployeeForm((current) => ({ ...initialEmployeeForm, site_id: current.site_id || employeeForm.site_id }))
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'Unable to create employee.')
    }
  }

  async function handleFaceUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setUploadMessage('')

    if (!selectedEmployeeId || !selectedFile) {
      setError('Choose an employee and a face image first.')
      return
    }

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const createdProfile = await apiRequest<EmployeeFaceProfile>(`/employees/${selectedEmployeeId}/face-profiles`, {
        method: 'POST',
        body: formData,
      })

      setEmployees((current) =>
        current.map((employee) =>
          employee.id === selectedEmployeeId
            ? { ...employee, face_profiles: [createdProfile, ...employee.face_profiles] }
            : employee,
        ),
      )
      setSelectedFile(null)
      setUploadMessage('Face profile uploaded successfully.')
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Unable to upload face image.')
    }
  }

  return (
    <div className="page-grid">
      <div className="page-grid page-grid--two-up">
        <Panel
          title="Create Employee"
          subtitle="Add the employee record first, then upload one or more clear face photos."
        >
          <form className="stack" onSubmit={handleEmployeeSubmit}>
            <label className="field">
              <span>Site</span>
              <select
                value={employeeForm.site_id}
                onChange={(event) =>
                  setEmployeeForm((current) => ({ ...current, site_id: event.target.value }))
                }
              >
                {sites.map((site) => (
                  <option key={site.id} value={site.id}>
                    {site.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Employee code</span>
              <input
                value={employeeForm.employee_code}
                onChange={(event) =>
                  setEmployeeForm((current) => ({ ...current, employee_code: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>First name</span>
              <input
                value={employeeForm.first_name}
                onChange={(event) =>
                  setEmployeeForm((current) => ({ ...current, first_name: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>Last name</span>
              <input
                value={employeeForm.last_name}
                onChange={(event) =>
                  setEmployeeForm((current) => ({ ...current, last_name: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>Role title</span>
              <input
                value={employeeForm.role_title}
                onChange={(event) =>
                  setEmployeeForm((current) => ({ ...current, role_title: event.target.value }))
                }
              />
            </label>
            {error ? <p className="form-error">{error}</p> : null}
            <button className="primary-button" disabled={!sites.length} type="submit">
              Create employee
            </button>
          </form>

          <form className="stack upload-panel" onSubmit={handleFaceUpload}>
            <div className="panel__header">
              <h3>Enroll Face</h3>
              <p>Use a front-facing image with one clear face.</p>
            </div>
            <label className="field">
              <span>Employee</span>
              <select value={selectedEmployeeId} onChange={(event) => selectEmployee(event.target.value)}>
                <option value="">Select employee</option>
                {employeeOptions.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Face image</span>
              <input type="file" accept="image/*" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
            </label>
            {uploadMessage ? <p className="form-success">{uploadMessage}</p> : null}
            <button className="ghost-button" disabled={!employeeOptions.length} type="submit">
              Upload face image
            </button>
          </form>
        </Panel>

        <Panel
          title="Employees"
          subtitle="Pick one employee to open the multi-day report below."
        >
          {employees.length ? (
            <div className="list">
              {employees.map((employee) => {
                const isSelected = employee.id === selectedEmployeeId
                return (
                  <article
                    key={employee.id}
                    className={`list-row list-row--top employee-card${isSelected ? ' employee-card--selected' : ''}`}
                  >
                    <div>
                      <strong>{employee.first_name} {employee.last_name}</strong>
                      <p>{employee.employee_code} | {employee.role_title || 'Role not set'}</p>
                      <small>{employee.face_profiles.length} face profile(s)</small>
                    </div>
                    <div className="stack-sm align-end">
                      <div className="employee-face-strip">
                        {employee.face_profiles.slice(0, 3).map((profile) => (
                          <img
                            key={profile.id}
                            className="employee-face-thumb"
                            src={`${API_ROOT}${profile.source_image_path}`}
                            alt={`${employee.first_name} ${employee.last_name}`}
                          />
                        ))}
                      </div>
                      <button className="ghost-button" type="button" onClick={() => selectEmployee(employee.id)}>
                        {isSelected ? 'Viewing report' : 'Open report'}
                      </button>
                    </div>
                  </article>
                )
              })}
            </div>
          ) : (
            <EmptyState message="No employees yet. Create one and upload a face image to begin recognition." />
          )}
        </Panel>
      </div>

      <Panel
        title="Employee Report"
        subtitle="This is the admin view for observed presence time, zone visits, violations, and a day-by-day timeline."
      >
        <div className="toolbar">
          <label className="field field--inline">
            <span>Employee</span>
            <select value={selectedEmployeeId} onChange={(event) => selectEmployee(event.target.value)}>
              <option value="">Select employee</option>
              {employeeOptions.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.label}
                </option>
              ))}
            </select>
          </label>

          <label className="field field--inline">
            <span>Range</span>
            <select value={reportDays} onChange={(event) => selectReportDays(Number(event.target.value))}>
              <option value={1}>Today</option>
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
            </select>
          </label>
        </div>

        {selectedEmployeeId && !report ? <p className="form-success">Loading employee report...</p> : null}
        {error ? <p className="form-error">{error}</p> : null}

        {selectedEmployeeId && report ? (
          <div className="stack">
            <article className="report-hero">
              <div>
                <strong>{report.employee.full_name}</strong>
                <p>
                  {report.employee.employee_code} | {report.employee.role_title || 'Role not set'} | {report.employee.site_name || 'No site'}
                </p>
                <small>
                  Report window: {formatDateTime(report.window_start)} to {formatDateTime(report.window_end)} | Timezone: {report.employee.timezone}
                </small>
              </div>
            </article>

            <div className="stats-grid">
              <article className="stat-card">
                <p>Observed Presence</p>
                <strong>{formatMinutes(report.totals.presence_minutes)}</strong>
              </article>
              <article className="stat-card">
                <p>Zone Visits</p>
                <strong>{report.totals.zone_visit_count}</strong>
              </article>
              <article className="stat-card">
                <p>Alerts</p>
                <strong>{report.totals.alert_count}</strong>
              </article>
              <article className="stat-card">
                <p>Violations</p>
                <strong>{report.totals.violation_count}</strong>
              </article>
              <article className="stat-card">
                <p>Sightings</p>
                <strong>{report.totals.sighting_count}</strong>
              </article>
              <article className="stat-card">
                <p>Observed Days</p>
                <strong>{report.totals.days_observed}</strong>
              </article>
            </div>

            <div className="page-grid page-grid--two-up">
              <Panel title="Top Zones" subtitle="This helps the admin see where the employee spent time most often.">
                {report.zone_visits.length ? (
                  <div className="list">
                    {report.zone_visits.map((zone) => (
                      <article key={zone.zone_name} className="list-row">
                        <div>
                          <strong>{zone.zone_name}</strong>
                          <p>{zone.visit_count} observed visit(s)</p>
                        </div>
                        <span className="pill">{zone.visit_count}</span>
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyState message="No zone visits recorded for this employee in the selected range." />
                )}
              </Panel>

              <Panel title="Recent Timeline" subtitle="Latest alerts and sightings for this employee.">
                {report.recent_timeline.length ? (
                  <div className="list">
                    {report.recent_timeline.map((item) => (
                      <article key={`${item.item_type}-${item.occurred_at}-${item.title}`} className="list-row list-row--top">
                        <div>
                          <strong>{item.title}</strong>
                          <p>{item.description}</p>
                          <small>{renderTimelineMeta(item)}</small>
                          <small>{formatDateTime(item.occurred_at)}</small>
                        </div>
                        <div className="stack-sm align-end">
                          <span className={`pill${item.severity ? ` pill--${item.severity}` : ''}`}>{item.item_type}</span>
                          {item.status ? <small>{item.status}</small> : null}
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyState message="No sightings or alerts recorded for this employee yet." />
                )}
              </Panel>
            </div>

            <Panel title="Day By Day" subtitle="This shows when the employee was first seen, last seen, and whether alerts happened that day.">
              {report.daily_summaries.length ? (
                <div className="list">
                  {report.daily_summaries.map(renderDaySummary)}
                </div>
              ) : (
                <EmptyState message="No daily activity has been recorded for this employee in the selected range." />
              )}
            </Panel>
          </div>
        ) : (
          <EmptyState message="Choose an employee to view the report." />
        )}
      </Panel>
    </div>
  )
}
