import React, { useState, useEffect, useRef } from 'react'

const SENSITIVE_PATTERNS = [/password/i, /^pwd$/i, /secret/i, /^otp$/i, /captcha/i, /cvv/i]

function isSensitiveField(key) {
  return SENSITIVE_PATTERNS.some(p => p.test(key))
}

const DynamicReviewForm = ({
  fields,
  editableRequired = [],
  editableOptional = [],
  canonicalFields = [],
  onConfirm,
  onInlineUpdate,
  submitting = false,
  savingInline = false,
  hasBlockers = false,
  readyForExecution = false,
}) => {
  const [localValues, setLocalValues] = useState({})
  const [expandPrefilled, setExpandPrefilled] = useState(false)
  const [expandOptional, setExpandOptional] = useState(false)
  const firstRequiredRef = useRef(null)

  useEffect(() => {
    const initial = {}
    fields.forEach(f => { initial[f.key] = f.value || '' })
    setLocalValues(initial)
  }, [fields])

  // Auto-scroll to first required field
  useEffect(() => {
    if (editableRequired.length > 0 && firstRequiredRef.current) {
      setTimeout(() => {
        firstRequiredRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }, 300)
    }
  }, [editableRequired])

  const handleChange = (key, val) => {
    setLocalValues(prev => ({ ...prev, [key]: val }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onConfirm(localValues)
  }

  // Save inline edits (only changed required/optional fields)
  const handleSaveInline = () => {
    const changedFields = {}
    const persistFlags = {}

    for (const f of [...editableRequired, ...editableOptional]) {
      const val = localValues[f.key]
      if (val && val !== f.value) {
        changedFields[f.key] = val
        // Auto-persist non-sensitive, non-password fields
        if (!isSensitiveField(f.key)) {
          persistFlags[f.key] = true
        }
      }
    }

    if (Object.keys(changedFields).length === 0) return
    onInlineUpdate(changedFields, persistFlags)
  }

  const renderField = (field, refProp) => {
    const value = localValues[field.key] || ''
    const sensitive = isSensitiveField(field.key)
    const common = {
      id: field.key,
      name: field.key,
      required: field.required,
      placeholder: field.placeholder || '',
      className: 'field-input',
      ref: refProp || undefined,
    }

    switch (field.field_type) {
      case 'textarea':
        return <textarea {...common} value={value} onChange={(e) => handleChange(field.key, e.target.value)} rows={4} />
      case 'select':
        return (
          <select {...common} value={value} onChange={(e) => handleChange(field.key, e.target.value)}>
            <option value="">-- Select --</option>
            {(field.options || []).map((opt, i) => <option key={i} value={opt.value}>{opt.label}</option>)}
          </select>
        )
      case 'radio':
        return (
          <div role="radiogroup" className="radio-group">
            {(field.options || []).map((opt, i) => (
              <label key={i} style={{ display: 'block', margin: '8px 0' }}>
                <input type="radio" name={field.key} value={opt.value} checked={value === opt.value} onChange={(e) => handleChange(field.key, e.target.value)} required={field.required} />
                <span style={{ marginLeft: '8px' }}>{opt.label}</span>
              </label>
            ))}
          </div>
        )
      case 'checkbox':
        if ((field.options || []).length > 0) {
          const checkedValues = typeof value === 'string' && value ? value.split(',') : []
          return (
            <div className="checkbox-group">
              {field.options.map((opt, i) => (
                <label key={i} style={{ display: 'block', margin: '8px 0' }}>
                  <input type="checkbox" name={field.key} value={opt.value} checked={checkedValues.includes(opt.value)}
                    onChange={(e) => {
                      const newVals = e.target.checked ? [...checkedValues, opt.value] : checkedValues.filter(v => v !== opt.value)
                      handleChange(field.key, newVals.join(','))
                    }} />
                  <span style={{ marginLeft: '8px' }}>{opt.label}</span>
                </label>
              ))}
            </div>
          )
        }
        return (
          <label><input type="checkbox" checked={value === 'true' || value === true} onChange={(e) => handleChange(field.key, e.target.checked ? 'true' : 'false')} /><span style={{ marginLeft: '8px' }}>{field.label}</span></label>
        )
      case 'file':
        return <div style={{ color: '#6366f1', fontSize: '0.85rem', padding: '0.5rem', background: 'rgba(99,102,241,0.06)', borderRadius: '6px' }}>📎 Managed via File Uploads section above</div>
      default:
        return <input {...common} type={sensitive ? 'password' : field.field_type} value={value} onChange={(e) => handleChange(field.key, e.target.value)} />
    }
  }

  const getSourceBadge = (source) => {
    const badges = {
      db: { text: 'From profile', color: '#155724', bg: '#d4edda' },
      session: { text: 'From session', color: '#0c5460', bg: '#d1ecf1' },
      llm: { text: 'AI matched', color: '#856404', bg: '#fff3cd' },
      none: { text: 'Not found', color: '#6c757d', bg: '#e2e3e5' }
    }
    return badges[source] || badges.none
  }

  const fileFields = fields.filter(f => f.field_type === 'file')
  const hasEmptyRequired = editableRequired.some(f => !localValues[f.key])
  const submitDisabled = submitting || hasBlockers || hasEmptyRequired

  return (
    <form onSubmit={handleSubmit} className="dynamic-form">

      {/* Section 1: Required — please complete (expanded, top priority) */}
      {editableRequired.length > 0 && (
        <div style={{ marginBottom: '2rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: '#dc2626', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ background: '#fef2f2', padding: '0.25rem 0.5rem', borderRadius: '6px', border: '1px solid #fecaca' }}>
              ⚠ {editableRequired.length} Required — Please Complete
            </span>
          </h3>
          {editableRequired.map((field, idx) => {
            const sensitive = isSensitiveField(field.key)
            return (
              <div key={field.key} ref={idx === 0 ? firstRequiredRef : undefined}
                style={{ marginBottom: '1.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.1)', borderLeft: '3px solid #f87171', paddingLeft: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <label style={{ fontWeight: 600 }}>
                    {field.label}
                    <span style={{ color: '#f87171' }}> * Required</span>
                    {sensitive && <span style={{ marginLeft: '0.5rem', fontSize: '0.75rem', color: '#9ca3af' }}>🔒 Not saved to profile</span>}
                  </label>
                </div>
                {renderField(field, idx === 0 ? firstRequiredRef : undefined)}
              </div>
            )
          })}

          {/* Save inline button */}
          <button type="button" className="btn btn-outline" onClick={handleSaveInline} disabled={savingInline}
            style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>
            {savingInline ? 'Saving...' : '💾 Save these fields'}
          </button>
        </div>
      )}

      {/* Section 2: Already filled (collapsed by default) */}
      {canonicalFields.length > 0 && (
        <div style={{ marginBottom: '2rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem', color: '#10b981', cursor: 'pointer', userSelect: 'none' }}
            onClick={() => setExpandPrefilled(!expandPrefilled)}>
            {expandPrefilled ? '▾' : '▸'} ✓ Pre-filled ({canonicalFields.length})
          </h3>
          {expandPrefilled && canonicalFields.map(field => {
            const badge = getSourceBadge(field.source)
            return (
              <div key={field.key} style={{ marginBottom: '1.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <label style={{ fontWeight: 600 }}>
                    {field.label}
                    {field.required && <span style={{ color: '#f87171' }}> *</span>}
                  </label>
                  <span style={{ fontSize: '0.75rem', padding: '0.25rem 0.75rem', borderRadius: '12px', background: badge.bg, color: badge.color }}>
                    {badge.text}
                  </span>
                </div>
                {field.matched_profile_key && <div style={{ fontSize: '0.75rem', color: '#666', marginBottom: '0.5rem' }}>Mapped from: {field.matched_profile_key}</div>}
                {renderField(field)}
              </div>
            )
          })}
        </div>
      )}

      {/* Section 3: Optional (collapsed by default) */}
      {editableOptional.length > 0 && (
        <div style={{ marginBottom: '2rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem', color: '#6366f1', cursor: 'pointer', userSelect: 'none' }}
            onClick={() => setExpandOptional(!expandOptional)}>
            {expandOptional ? '▾' : '▸'} ✎ Optional ({editableOptional.length})
          </h3>
          {expandOptional && editableOptional.map(field => (
            <div key={field.key} style={{ marginBottom: '1.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <label style={{ fontWeight: 600 }}>{field.label}</label>
                <span style={{ fontSize: '0.75rem', padding: '0.25rem 0.75rem', borderRadius: '12px', background: '#e2e3e5', color: '#6c757d' }}>Optional</span>
              </div>
              {renderField(field)}
            </div>
          ))}
        </div>
      )}

      {/* Section 4: File uploads */}
      {fileFields.length > 0 && (
        <div style={{ marginBottom: '2rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: '#6366f1' }}>📎 File Uploads ({fileFields.length})</h3>
          {fileFields.map(field => (
            <div key={field.key} style={{ marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
              <label style={{ fontWeight: 600 }}>{field.label}{field.required && <span style={{ color: '#f87171' }}> *</span>}</label>
              {renderField(field)}
            </div>
          ))}
        </div>
      )}

      <div className="form-actions review-actions">
        <button type="submit" className="btn btn-primary" disabled={submitDisabled}
          title={hasBlockers ? 'Resolve blockers first' : hasEmptyRequired ? 'Fill all required fields first' : ''}>
          {submitting ? 'Confirming...' :
            hasBlockers ? '🚫 Resolve Blockers First' :
            hasEmptyRequired ? `Fill ${editableRequired.filter(f => !localValues[f.key]).length} Required Fields First` :
            'Confirm & Start Filling →'}
        </button>
      </div>
    </form>
  )
}

export default DynamicReviewForm
