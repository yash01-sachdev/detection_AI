import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { apiRequest } from '../../lib/api/client'
import type { User } from '../../types/models'

const initialForm = {
  full_name: '',
  email: '',
  password: '',
}

export function AdminsPage() {
  const [admins, setAdmins] = useState<User[]>([])
  const [form, setForm] = useState(initialForm)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    apiRequest<User[]>('/admins')
      .then((loadedAdmins) => {
        setAdmins(loadedAdmins)
        setError('')
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load admins.')
      })
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSuccess('')

    try {
      const createdAdmin = await apiRequest<User>('/admins', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      setAdmins((current) => [createdAdmin, ...current])
      setForm(initialForm)
      setSuccess('Admin account created.')
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'Unable to create admin.')
    }
  }

  return (
    <div className="page-grid page-grid--two-up">
      <Panel
        title="Create Admin"
        subtitle="Create another administrator who can sign in with email and password."
      >
        <form className="stack" onSubmit={handleSubmit}>
          <label className="field">
            <span>Full name</span>
            <input
              value={form.full_name}
              onChange={(event) => setForm((current) => ({ ...current, full_name: event.target.value }))}
              placeholder="Operations Lead"
            />
          </label>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={form.email}
              onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              placeholder="admin@company.com"
            />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              placeholder="At least 8 characters"
            />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          {success ? <p className="form-success">{success}</p> : null}
          <button className="primary-button" type="submit">
            Create admin
          </button>
        </form>
      </Panel>

      <Panel
        title="Admin Accounts"
        subtitle="Only administrator accounts can access this dashboard."
      >
        {admins.length ? (
          <div className="list">
            {admins.map((admin) => (
              <article key={admin.id} className="list-row list-row--top">
                <div>
                  <strong>{admin.full_name}</strong>
                  <p>{admin.email}</p>
                  <small>{admin.role}</small>
                </div>
                <div className="stack-sm align-end">
                  <span className={`pill${admin.is_active ? ' pill--low' : ''}`}>
                    {admin.is_active ? 'active' : 'inactive'}
                  </span>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState message="No admin accounts found yet." />
        )}
      </Panel>
    </div>
  )
}
