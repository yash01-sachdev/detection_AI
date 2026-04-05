import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { API_BASE_URL, apiRequest } from '../../lib/api/client'
import type { Employee, EmployeeFaceProfile, Site } from '../../types/models'

const API_ROOT = API_BASE_URL.replace(/\/api\/v1\/?$/, '')

const initialEmployeeForm = {
  site_id: '',
  employee_code: '',
  first_name: '',
  last_name: '',
  role_title: '',
  is_active: true,
}

export function EmployeesPage() {
  const [sites, setSites] = useState<Site[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [employeeForm, setEmployeeForm] = useState(initialEmployeeForm)
  const [selectedEmployeeId, setSelectedEmployeeId] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
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

  const employeeOptions = useMemo(
    () =>
      employees.map((employee) => ({
        id: employee.id,
        label: `${employee.first_name} ${employee.last_name} (${employee.employee_code})`,
      })),
    [employees],
  )

  async function handleEmployeeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    try {
      const createdEmployee = await apiRequest<Employee>('/employees', {
        method: 'POST',
        body: JSON.stringify(employeeForm),
      })
      setEmployees((current) => [createdEmployee, ...current])
      setSelectedEmployeeId(createdEmployee.id)
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
            <select value={selectedEmployeeId} onChange={(event) => setSelectedEmployeeId(event.target.value)}>
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
        subtitle="Face profiles uploaded here become candidates for live recognition in the worker."
      >
        {employees.length ? (
          <div className="list">
            {employees.map((employee) => (
              <article key={employee.id} className="list-row list-row--top">
                <div>
                  <strong>{employee.first_name} {employee.last_name}</strong>
                  <p>{employee.employee_code} | {employee.role_title || 'Role not set'}</p>
                  <small>{employee.face_profiles.length} face profile(s)</small>
                </div>
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
              </article>
            ))}
          </div>
        ) : (
          <EmptyState message="No employees yet. Create one and upload a face image to begin recognition." />
        )}
      </Panel>
    </div>
  )
}
