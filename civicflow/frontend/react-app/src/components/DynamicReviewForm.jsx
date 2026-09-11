import React, { useState, useEffect, useRef } from 'react'
import { Paperclip, AlertTriangle, Lock, ChevronDown, ChevronRight, Check, ArrowRight } from 'lucide-react'

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
              <label key={i}>
                <input type="radio" name={field.key} value={opt.value} checked={value === opt.value} onChange={(e) => handleChange(field.key, e.target.value)} required={field.required} />
                <span>{opt.label}</span>
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
                <label key={i}>
                  <input type="checkbox" name={field.key} value={opt.value} checked={checkedValues.includes(opt.value)}
                    onChange={(e) => {
                      const newVals = e.target.checked ? [...checkedValues, opt.value] : checkedValues.filter(v => v !== opt.value)
                      handleChange(field.key, newVals.join(','))
                    }} />
                  <span>{opt.label}</span>
                </label>
              ))}
            </div>
          )
        }
        return (
          <label>
            <input type="checkbox" checked={value === 'true' || value === true} onChange={(e) => handleChange(field.key, e.target.checked ? 'true' : 'false')} />
            <span style={{ marginLeft: '8px' }}>{field.label}</span>
          </label>
        )
      case 'file':
        return (
          <div className="file-managed-indicator">
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Paperclip size={14} /> Managed via File Uploads section above</span>
          </div>
        )
      default:
        return <input {...common} type={sensitive ? 'password' : field.field_type} value={value} onChange={(e) => handleChange(field.key, e.target.value)} />
    }
  }

  const getSourceBadgeClass = (source) => {
    const map = { db: 'source-badge--db', session: 'source-badge--session', llm: 'source-badge--llm', none: 'source-badge--none' }
    return map[source] || 'source-badge--none'
  }

  const getSourceBadgeText = (source) => {
    const map = { db: 'From profile', session: 'From session', llm: 'AI matched', none: 'Not found' }
    return map[source] || 'Not found'
  }

  const fileFields = fields.filter(f => f.field_type === 'file')
  const hasEmptyRequired = editableRequired.some(f => !localValues[f.key])
  const submitDisabled = submitting || hasBlockers || hasEmptyRequired

  return (
    <form onSubmit={handleSubmit} className="dynamic-form">

      {/* ── Section 1: Required — please complete (expanded, top priority) ── */}
      {editableRequired.length > 0 && (
        <div className="dynamic-section">
          <h3 className="required-section-heading">
            <span className="required-section-badge">
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><AlertTriangle size={18} /> {editableRequired.length} Required — Please Complete</span>
            </span>
          </h3>

          {editableRequired.map((field, idx) => {
            const sensitive = isSensitiveField(field.key)
            return (
              <div
                key={field.key}
                className="required-field-row"
                ref={idx === 0 ? firstRequiredRef : undefined}
              >
                <div className="field-row-header">
                  <label className="field-row-label" htmlFor={field.key}>
                    {field.label}
                    <span className="field-required-tag">* Required</span>
                    {sensitive && <span className="field-sensitive-tag"><Lock size={12} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '2px' }} /> Not saved</span>}
                  </label>
                </div>
                {renderField(field, idx === 0 ? firstRequiredRef : undefined)}
              </div>
            )
          })}

          <div className="save-inline-row">
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={handleSaveInline}
              disabled={savingInline}
            >
              {savingInline ? 'Saving...' : '💾 Save these fields'}
            </button>
          </div>
        </div>
      )}

      {/* ── Section 2: Already filled (collapsed by default) ── */}
      {canonicalFields.length > 0 && (
        <div className="dynamic-section">
          <h3
            className={`collapsible-heading heading-prefilled`}
            onClick={() => setExpandPrefilled(!expandPrefilled)}
            aria-expanded={expandPrefilled}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>{expandPrefilled ? <ChevronDown size={16} /> : <ChevronRight size={16} />} <Check size={14} /> Pre-filled ({canonicalFields.length})</div>
          </h3>
          {expandPrefilled && canonicalFields.map(field => (
            <div key={field.key} className="prefilled-field-row">
              <div className="field-row-header">
                <label className="field-row-label" htmlFor={field.key}>
                  {field.label}
                  {field.required && <span className="field-required-tag">*</span>}
                </label>
                <span className={`source-badge ${getSourceBadgeClass(field.source)}`}>
                  {getSourceBadgeText(field.source)}
                </span>
              </div>
              {field.matched_profile_key && (
                <div className="field-mapped-from">Mapped from: {field.matched_profile_key}</div>
              )}
              {renderField(field)}
            </div>
          ))}
        </div>
      )}

      {/* ── Section 3: Optional (collapsed by default) ── */}
      {editableOptional.length > 0 && (
        <div className="dynamic-section">
          <h3
            className="collapsible-heading heading-optional"
            onClick={() => setExpandOptional(!expandOptional)}
            aria-expanded={expandOptional}
          >
            {expandOptional ? '▾' : '▸'} ✎ Optional ({editableOptional.length})
          </h3>
          {expandOptional && editableOptional.map(field => (
            <div key={field.key} className="optional-field-row">
              <div className="field-row-header">
                <label className="field-row-label" htmlFor={field.key}>{field.label}</label>
                <span className="badge badge-optional">Optional</span>
              </div>
              {renderField(field)}
            </div>
          ))}
        </div>
      )}

      {/* ── Section 4: File uploads ── */}
      {fileFields.length > 0 && (
        <div className="dynamic-section">
          <h3 className="collapsible-heading heading-optional" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Paperclip size={18} /> File Uploads ({fileFields.length})</h3>
          {fileFields.map(field => (
            <div key={field.key} className="optional-field-row">
              <label className="field-row-label" htmlFor={field.key}>
                {field.label}
                {field.required && <span className="field-required-tag">*</span>}
              </label>
              {renderField(field)}
            </div>
          ))}
        </div>
      )}

      <div className="form-actions review-actions">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={submitDisabled}
          title={hasBlockers ? 'Resolve blockers first' : hasEmptyRequired ? 'Fill all required fields first' : ''}
        >
          {submitting ? 'Confirming...' :
            hasBlockers ? '🚫 Resolve Blockers First' :
            hasEmptyRequired ? `Fill ${editableRequired.filter(f => !localValues[f.key]).length} Required Fields First` :
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>Confirm & Start Filling <ArrowRight size={16} /></span>}
        </button>
      </div>
    </form>
  )
}

export default DynamicReviewForm
