import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { apiRequest } from '../../lib/api/client'
import type { Rule, Site, Zone } from '../../types/models'

const initialRuleForm = {
  site_id: '',
  zone_id: '',
  entity_type: 'employee',
  posture: '',
  severity: 'high',
  name: '',
  description: '',
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function createTemplateKey(name: string, zoneId: string, entityType: string, posture: string) {
  const postureSuffix = posture ? `_${posture}` : ''
  const base = slugify(name) || `${entityType}${postureSuffix}_zone_rule`
  return `${base}_${zoneId.slice(0, 8)}`
}

function describeRule(rule: Rule, zonesById: Record<string, Zone>) {
  const entityType = String(rule.conditions.entity_type ?? 'anything')
  const posture = typeof rule.conditions.posture === 'string' ? rule.conditions.posture : ''
  const zoneId = typeof rule.conditions.zone_id === 'string' ? rule.conditions.zone_id : ''
  const zoneType = typeof rule.conditions.zone_type === 'string' ? rule.conditions.zone_type : ''
  const zoneLabel = zoneId
    ? zonesById[zoneId]?.name || 'selected zone'
    : (zoneType || 'any zone').replace(/_/g, ' ')
  const subjectLabel = posture
    ? `${entityType.replace(/_/g, ' ')} shows ${posture.replace(/_/g, ' ')} posture`
    : `${entityType.replace(/_/g, ' ')} enters`

  return `If ${subjectLabel} in ${zoneLabel}, create ${rule.severity} alert`
}

export function RulesPage() {
  const [sites, setSites] = useState<Site[]>([])
  const [zones, setZones] = useState<Zone[]>([])
  const [rules, setRules] = useState<Rule[]>([])
  const [selectedSiteId, setSelectedSiteId] = useState('')
  const [form, setForm] = useState(initialRuleForm)
  const [error, setError] = useState('')
  const [saveMessage, setSaveMessage] = useState('')

  useEffect(() => {
    Promise.all([
      apiRequest<Site[]>('/sites'),
      apiRequest<Zone[]>('/zones'),
      apiRequest<Rule[]>('/rules'),
    ])
      .then(([loadedSites, loadedZones, loadedRules]) => {
        setSites(loadedSites)
        setZones(loadedZones)
        setRules(loadedRules)
        if (loadedSites.length) {
          const firstSiteId = loadedSites[0].id
          setSelectedSiteId(firstSiteId)
          const firstSiteZone = loadedZones.find((zone) => zone.site_id === firstSiteId)
          setForm((current) => ({
            ...current,
            site_id: current.site_id || firstSiteId,
            zone_id: current.zone_id || firstSiteZone?.id || '',
          }))
        }
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load rules.')
      })
  }, [])

  const zonesById = useMemo(
    () =>
      Object.fromEntries(
        zones.map((zone) => [zone.id, zone]),
      ) as Record<string, Zone>,
    [zones],
  )

  const formZones = useMemo(
    () => zones.filter((zone) => zone.site_id === form.site_id),
    [form.site_id, zones],
  )

  const filteredRules = useMemo(
    () => (selectedSiteId ? rules.filter((rule) => rule.site_id === selectedSiteId) : rules),
    [rules, selectedSiteId],
  )

  const selectedZone = form.zone_id ? zonesById[form.zone_id] : null
  const previewSummary = selectedZone
    ? form.posture
      ? `If ${form.entity_type} shows ${form.posture.replace(/_/g, ' ')} in ${selectedZone.name}, create ${form.severity} alert.`
      : `If ${form.entity_type} enters ${selectedZone.name}, create ${form.severity} alert.`
    : 'Pick a site and zone to preview the rule.'

  function handleFormSiteChange(siteId: string) {
    const firstSiteZone = zones.find((zone) => zone.site_id === siteId)
    setForm((current) => ({
      ...current,
      site_id: siteId,
      zone_id: firstSiteZone?.id || '',
    }))
    setSaveMessage('')
    setError('')
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSaveMessage('')

    if (!form.site_id) {
      setError('Choose a site first.')
      return
    }

    if (!form.zone_id) {
      setError('Choose a zone first.')
      return
    }

    const zone = zonesById[form.zone_id]
    if (!zone) {
      setError('Selected zone could not be found.')
      return
    }

    const trimmedName = form.name.trim()
    if (trimmedName.length < 2) {
      setError('Rule name must be at least 2 characters.')
      return
    }

    const payload = {
      site_id: form.site_id,
      applies_to_site_type: null,
      template_key: createTemplateKey(trimmedName, zone.id, form.entity_type, form.posture),
      name: trimmedName,
      description:
        form.description.trim() ||
        (form.posture
          ? `Alert when ${form.entity_type} shows ${form.posture.replace(/_/g, ' ')} in ${zone.name}.`
          : `Alert when ${form.entity_type} enters ${zone.name}.`),
      conditions: {
        entity_type: form.entity_type,
        zone_id: zone.id,
        ...(form.posture ? { posture: form.posture } : {}),
      },
      actions: {
        create_alert: true,
        snapshot: true,
      },
      severity: form.severity,
      is_default: false,
      is_enabled: true,
    }

    try {
      const createdRule = await apiRequest<Rule>('/rules', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setRules((current) => [createdRule, ...current])
      setSaveMessage('Custom rule saved successfully.')
      setSelectedSiteId(form.site_id)
      setForm((current) => ({
        ...current,
        name: '',
        description: '',
      }))
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'Unable to save rule.')
    }
  }

  return (
    <div className="page-grid page-grid--two-up">
      <Panel
        title="Create Custom Rule"
        subtitle="Use the zones you already drew to say exactly who should trigger an alert in that area."
      >
        <form className="stack" onSubmit={handleSubmit}>
          <div className="rule-builder-grid">
            <label className="field">
              <span>Site</span>
              <select value={form.site_id} onChange={(event) => handleFormSiteChange(event.target.value)}>
                {sites.map((site) => (
                  <option key={site.id} value={site.id}>
                    {site.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Zone</span>
              <select
                value={form.zone_id}
                onChange={(event) =>
                  setForm((current) => ({ ...current, zone_id: event.target.value }))
                }
              >
                <option value="">Select zone</option>
                {formZones.map((zone) => (
                  <option key={zone.id} value={zone.id}>
                    {zone.name} ({zone.zone_type})
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="rule-builder-grid">
            <label className="field">
              <span>Who should trigger it</span>
              <select
                value={form.entity_type}
                onChange={(event) =>
                  setForm((current) => ({ ...current, entity_type: event.target.value }))
                }
              >
                <option value="person">Person</option>
                <option value="employee">Recognized employee</option>
                <option value="dog">Dog</option>
                <option value="vehicle">Vehicle</option>
              </select>
            </label>

            <label className="field">
              <span>Optional posture</span>
              <select
                value={form.posture}
                onChange={(event) =>
                  setForm((current) => ({ ...current, posture: event.target.value }))
                }
              >
                <option value="">Any zone entry</option>
                <option value="inactive">Inactive</option>
                <option value="head_down">Head-down posture</option>
                <option value="fallen">Fall-like posture</option>
              </select>
            </label>

            <label className="field">
              <span>Severity</span>
              <select
                value={form.severity}
                onChange={(event) =>
                  setForm((current) => ({ ...current, severity: event.target.value }))
                }
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </label>
          </div>

          <label className="field">
            <span>Rule name</span>
            <input
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({ ...current, name: event.target.value }))
              }
              placeholder="Employee In Smoking Area"
            />
          </label>

          <label className="field">
            <span>Description</span>
            <textarea
              rows={3}
              value={form.description}
              onChange={(event) =>
                setForm((current) => ({ ...current, description: event.target.value }))
              }
              placeholder="Optional. Leave blank to auto-generate a simple description."
            />
          </label>

          <article className="rule-summary-card">
            <strong>Rule preview</strong>
            <p>{previewSummary}</p>
          </article>

          {error ? <p className="form-error">{error}</p> : null}
          {saveMessage ? <p className="form-success">{saveMessage}</p> : null}

          <button className="primary-button" disabled={!sites.length || !formZones.length} type="submit">
            Save custom rule
          </button>
        </form>
      </Panel>

      <Panel
        title="Rules"
        subtitle="Default rules come from the site mode. Custom rules let you target exact zones like a specific smoking area or room."
      >
        <div className="toolbar">
          <label className="field field--inline">
            <span>Filter by site</span>
            <select
              value={selectedSiteId}
              onChange={(event) => setSelectedSiteId(event.target.value)}
            >
              <option value="">All sites</option>
              {sites.map((site) => (
                <option key={site.id} value={site.id}>
                  {site.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error ? <p className="form-error">{error}</p> : null}

        {filteredRules.length ? (
          <div className="list">
            {filteredRules.map((rule) => (
              <article key={rule.id} className="list-row list-row--top">
                <div>
                  <strong>{rule.name}</strong>
                  <p>{rule.description || describeRule(rule, zonesById)}</p>
                  <small>{describeRule(rule, zonesById)}</small>
                </div>
                <div className="stack-sm align-end">
                  <span className={`pill pill--${rule.severity}`}>{rule.severity}</span>
                  <small>{rule.is_default ? 'default rule' : 'custom rule'}</small>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState message="No rules found yet. Create a site for defaults or save a custom rule here." />
        )}
      </Panel>
    </div>
  )
}
