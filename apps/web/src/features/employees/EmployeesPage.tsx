import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { API_BASE_URL, apiRequest } from '../../lib/api/client'
import type {
  Employee,
  EmployeeAttendanceDay,
  EmployeeDaySummary,
  EmployeeFaceProfile,
  EmployeeReport,
  EmployeeTimelineItem,
  EmployeeZoneVisitStat,
  Site,
} from '../../types/models'

const API_ROOT = API_BASE_URL.replace(/\/api\/v1\/?$/, '')
const weekdayOptions = [
  { key: 'mon', label: 'Mon' },
  { key: 'tue', label: 'Tue' },
  { key: 'wed', label: 'Wed' },
  { key: 'thu', label: 'Thu' },
  { key: 'fri', label: 'Fri' },
  { key: 'sat', label: 'Sat' },
  { key: 'sun', label: 'Sun' },
]

const initialEmployeeForm = {
  site_id: '',
  employee_code: '',
  first_name: '',
  last_name: '',
  role_title: '',
  shift_name: 'Day Shift',
  shift_start_time: '09:00',
  shift_end_time: '17:00',
  shift_grace_minutes: 10,
  shift_days: ['mon', 'tue', 'wed', 'thu', 'fri'],
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

function formatSeconds(seconds: number) {
  if (seconds < 60) {
    return `${seconds} sec`
  }

  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (!remainingSeconds) {
    return `${minutes} min`
  }
  return `${minutes} min ${remainingSeconds} sec`
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

function formatShiftDays(days: string[]) {
  if (!days.length) {
    return 'No working days set'
  }

  return days
    .map((day) => weekdayOptions.find((option) => option.key === day)?.label ?? day)
    .join(', ')
}

function formatShiftWindow(shiftStartTime: string, shiftEndTime: string, shiftDays: string[]) {
  return `${shiftStartTime} - ${shiftEndTime} | ${formatShiftDays(shiftDays)}`
}

function renderAttendanceStatus(day: EmployeeAttendanceDay) {
  if (day.status === 'on_time') {
    return 'On time'
  }
  if (day.status === 'late') {
    return 'Late'
  }
  if (day.status === 'missed') {
    return 'Missed'
  }
  if (day.status === 'off_day_activity') {
    return 'Activity on off day'
  }
  return day.status.replace(/_/g, ' ')
}

function attendancePillClass(status: string) {
  if (status === 'missed') {
    return 'pill pill--critical'
  }
  if (status === 'late') {
    return 'pill pill--medium'
  }
  return 'pill pill--low'
}

function renderArrivalDelta(minutes: number | null) {
  if (minutes === null) {
    return 'No arrival recorded'
  }
  if (minutes === 0) {
    return 'Arrived exactly at shift start'
  }
  if (minutes < 0) {
    return `${Math.abs(minutes)} min early`
  }
  return `${minutes} min late`
}

function renderDaySummary(day: EmployeeDaySummary) {
  return (
    <article key={day.date} className="list-row list-row--top">
      <div>
        <strong>{day.date}</strong>
        <p>
          Presence: {formatMinutes(day.presence_minutes)} | Sightings: {day.sighting_count} | Alerts: {day.alert_count}
        </p>
        <small>Inactive periods: {day.inactivity_event_count}</small>
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

function renderAttendanceDay(day: EmployeeAttendanceDay) {
  return (
    <article key={`${day.date}-${day.status}`} className="list-row list-row--top">
      <div>
        <strong>{day.date}</strong>
        <p>{renderAttendanceStatus(day)}</p>
        <small>
          First seen: {formatDateTime(day.first_seen_at)} | Last seen: {formatDateTime(day.last_seen_at)}
        </small>
        <small>
          Arrival: {renderArrivalDelta(day.arrival_delta_minutes)} | Outside-shift sightings: {day.outside_shift_sighting_count}
        </small>
      </div>
      <div className="stack-sm align-end">
        <span className={attendancePillClass(day.status)}>{renderAttendanceStatus(day)}</span>
      </div>
    </article>
  )
}

export function EmployeesPage() {
  const [sites, setSites] = useState<Site[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [employeeForm, setEmployeeForm] = useState(initialEmployeeForm)
  const [selectedEmployeeId, setSelectedEmployeeId] = useState('')
  const [uploadEmployeeId, setUploadEmployeeId] = useState('')
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
          setUploadEmployeeId(loadedEmployees[0].id)
        }
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load employees.')
      })
  }, [])

  useEffect(() => {
    const employeeIds = new Set(employees.map((employee) => employee.id))
    if (selectedEmployeeId && !employeeIds.has(selectedEmployeeId)) {
      setSelectedEmployeeId(employees[0]?.id ?? '')
    }
    if (uploadEmployeeId && !employeeIds.has(uploadEmployeeId)) {
      setUploadEmployeeId('')
    }
    if (!uploadEmployeeId) {
      if (selectedEmployeeId && employeeIds.has(selectedEmployeeId)) {
        setUploadEmployeeId(selectedEmployeeId)
      } else if (employees.length) {
        setUploadEmployeeId(employees[0].id)
      }
    }
  }, [employees, selectedEmployeeId, uploadEmployeeId])

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
    setUploadEmployeeId(employeeId)
    setReport(null)
    setUploadMessage('')
  }

  async function handleDeleteEmployee(employeeId: string) {
    const employee = employees.find((item) => item.id === employeeId)
    if (!employee) {
      return
    }

    const shouldDelete = window.confirm(
      `Delete ${employee.first_name} ${employee.last_name} (${employee.employee_code})? This will also remove uploaded face images.`,
    )
    if (!shouldDelete) {
      return
    }

    setError('')
    setUploadMessage('')

    try {
      await apiRequest<void>(`/employees/${employeeId}`, { method: 'DELETE' })

      const remainingEmployees = employees.filter((item) => item.id !== employeeId)
      setEmployees(remainingEmployees)

      if (selectedEmployeeId === employeeId) {
        const nextSelectedEmployeeId = remainingEmployees[0]?.id ?? ''
        setSelectedEmployeeId(nextSelectedEmployeeId)
        setReport(null)
      }
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Unable to delete employee.')
    }
  }

  function selectReportDays(days: number) {
    setReportDays(days)
    setReport(null)
  }

  function toggleShiftDay(dayKey: string) {
    setEmployeeForm((current) => {
      const nextDays = current.shift_days.includes(dayKey)
        ? current.shift_days.filter((day) => day !== dayKey)
        : [...current.shift_days, dayKey]

      return {
        ...current,
        shift_days: weekdayOptions
          .map((option) => option.key)
          .filter((day) => nextDays.includes(day)),
      }
    })
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
      setUploadEmployeeId(createdEmployee.id)
      setEmployeeForm((current) => ({ ...initialEmployeeForm, site_id: current.site_id || employeeForm.site_id }))
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'Unable to create employee.')
    }
  }

  async function handleFaceUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setUploadMessage('')

    if (!uploadEmployeeId || !selectedFile) {
      setError('Choose an employee and a face image first.')
      return
    }

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const createdProfile = await apiRequest<EmployeeFaceProfile>(`/employees/${uploadEmployeeId}/face-profiles`, {
        method: 'POST',
        body: formData,
      })

      setEmployees((current) =>
        current.map((employee) =>
          employee.id === uploadEmployeeId
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
          subtitle="Add the employee record, define the shift schedule, then upload one or more clear face photos."
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
            <label className="field">
              <span>Shift name</span>
              <input
                value={employeeForm.shift_name}
                onChange={(event) =>
                  setEmployeeForm((current) => ({ ...current, shift_name: event.target.value }))
                }
              />
            </label>
            <div className="page-grid page-grid--two-up">
              <label className="field">
                <span>Shift start</span>
                <input
                  type="time"
                  value={employeeForm.shift_start_time}
                  onChange={(event) =>
                    setEmployeeForm((current) => ({ ...current, shift_start_time: event.target.value }))
                  }
                />
              </label>
              <label className="field">
                <span>Shift end</span>
                <input
                  type="time"
                  value={employeeForm.shift_end_time}
                  onChange={(event) =>
                    setEmployeeForm((current) => ({ ...current, shift_end_time: event.target.value }))
                  }
                />
              </label>
            </div>
            <label className="field">
              <span>Grace minutes</span>
              <input
                type="number"
                min={0}
                max={180}
                value={employeeForm.shift_grace_minutes}
                onChange={(event) =>
                  setEmployeeForm((current) => ({
                    ...current,
                    shift_grace_minutes: Number(event.target.value || 0),
                  }))
                }
              />
            </label>
            <div className="field">
              <span>Working days</span>
              <div className="toolbar">
                {weekdayOptions.map((day) => (
                  <label key={day.key} className="field field--inline">
                    <input
                      type="checkbox"
                      checked={employeeForm.shift_days.includes(day.key)}
                      onChange={() => toggleShiftDay(day.key)}
                    />
                    <span>{day.label}</span>
                  </label>
                ))}
              </div>
            </div>
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
              <select value={uploadEmployeeId} onChange={(event) => setUploadEmployeeId(event.target.value)}>
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
            {uploadEmployeeId ? (
              <p className="form-success">
                Upload target:{' '}
                {employeeOptions.find((employee) => employee.id === uploadEmployeeId)?.label ?? 'Selected employee'}
              </p>
            ) : null}
            {uploadMessage ? <p className="form-success">{uploadMessage}</p> : null}
            <button className="ghost-button" disabled={!employeeOptions.length || !uploadEmployeeId || !selectedFile} type="submit">
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
                      <small>{employee.shift_name} | {formatShiftWindow(employee.shift_start_time, employee.shift_end_time, employee.shift_days)}</small>
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
                      <button className="ghost-button" type="button" onClick={() => handleDeleteEmployee(employee.id)}>
                        Delete employee
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
                  Shift: {report.employee.shift_name} | {formatShiftWindow(report.employee.shift_start_time, report.employee.shift_end_time, report.employee.shift_days)}
                </small>
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
              <article className="stat-card">
                <p>Inactive Periods</p>
                <strong>{report.totals.inactivity_event_count}</strong>
              </article>
              <article className="stat-card">
                <p>Longest Inactive</p>
                <strong>{formatSeconds(report.totals.longest_inactivity_seconds)}</strong>
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
                          {item.inactive_seconds ? <small>Inactive duration: {formatSeconds(item.inactive_seconds)}</small> : null}
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

            <Panel
              title="Shift Attendance"
              subtitle="This compares actual sightings against the employee's planned shift."
            >
              <div className="stats-grid">
                <article className="stat-card">
                  <p>Scheduled Days</p>
                  <strong>{report.attendance_totals.scheduled_days}</strong>
                </article>
                <article className="stat-card">
                  <p>Attended Days</p>
                  <strong>{report.attendance_totals.attended_days}</strong>
                </article>
                <article className="stat-card">
                  <p>On-Time Days</p>
                  <strong>{report.attendance_totals.on_time_days}</strong>
                </article>
                <article className="stat-card">
                  <p>Late Days</p>
                  <strong>{report.attendance_totals.late_days}</strong>
                </article>
                <article className="stat-card">
                  <p>Missed Days</p>
                  <strong>{report.attendance_totals.missed_days}</strong>
                </article>
                <article className="stat-card">
                  <p>Off-Day Activity</p>
                  <strong>{report.attendance_totals.off_day_activity_days}</strong>
                </article>
                <article className="stat-card">
                  <p>Outside Shift Sightings</p>
                  <strong>{report.attendance_totals.outside_shift_sighting_count}</strong>
                </article>
              </div>

              {report.attendance_days.length ? (
                <div className="list">
                  {report.attendance_days.map(renderAttendanceDay)}
                </div>
              ) : (
                <EmptyState message="No shift attendance data is available in the selected range yet." />
              )}
            </Panel>

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
