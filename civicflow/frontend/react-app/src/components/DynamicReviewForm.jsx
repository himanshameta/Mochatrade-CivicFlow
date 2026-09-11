import React, { useState, useEffect } from 'react'

const DynamicReviewForm = ({ fields, onConfirm, submitting = false }) => {
  const [localValues, setLocalValues] = useState({})

  useEffect(() => {
    const initial = {}
    fields.forEach(f => {
      initial[f.key] = f.value || ''
    })
    setLocalValues(initial)
  }, [fields])

  const handleChange = (key, val) => {
    setLocalValues(prev => ({ ...prev, [key]: val }))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    onConfirm(localValues)
  }

  const renderField = (field) => {
    const value = localValues[field.key] || ''
    const common = {
      id: field.key,
      name: field.key,
      required: field.required,
      placeholder: field.placeholder || '',
      className: 'field-input'
    }

    switch (field.field_type) {
      case 'textarea':
        return (
          <textarea 
            {...common} 
            value={value} 
            onChange={(e) => handleChange(field.key, e.target.value)} 
            rows={4} 
          />
        )
      
      case 'select':
        return (
          <select 
            {...common} 
            value={value} 
            onChange={(e) => handleChange(field.key, e.target.value)}
          >
            <option value="">-- Select --</option>
            {(field.options || []).map((opt, i) => (
              <option key={i} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        )
      
      case 'radio':
        return (
          <div role="radiogroup" className="radio-group">
            {(field.options || []).map((opt, i) => (
              <label key={i} className="radio-label" style={{display:'block', margin:'8px 0'}}>
                <input 
                  type="radio" 
                  name={field.key} 
                  value={opt.value} 
                  checked={value === opt.value} 
                  onChange={(e) => handleChange(field.key, e.target.value)} 
                  required={field.required}
                />
                <span style={{marginLeft:'8px'}}>{opt.label}</span>
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
                <label key={i} className="checkbox-label" style={{display:'block', margin:'8px 0'}}>
                  <input
                    type="checkbox"
                    name={field.key}
                    value={opt.value}
                    checked={checkedValues.includes(opt.value)}
                    onChange={(e) => {
                      const newVals = e.target.checked
                        ? [...checkedValues, opt.value]
                        : checkedValues.filter(v => v !== opt.value);
                      handleChange(field.key, newVals.join(','));
                    }}
                  />
                  <span style={{marginLeft:'8px'}}>{opt.label}</span>
                </label>
              ))}
            </div>
          )
        } else {
          return (
            <label className="checkbox-label">
              <input 
                type="checkbox" 
                checked={value === 'true' || value === true} 
                onChange={(e) => handleChange(field.key, e.target.checked ? 'true' : 'false')}
              />
              <span style={{marginLeft:'8px'}}>{field.label}</span>
            </label>
          )
        }
      
      case 'file':
        return (
          <div className="file-field" style={{color:'#999'}}>
            <p className="file-note">This field requires file upload on the original portal: {field.label}</p>
          </div>
        )
      
      default:
        return (
          <input 
            {...common} 
            type={field.field_type} 
            value={value} 
            onChange={(e) => handleChange(field.key, e.target.value)}
          />
        )
    }
  }

  const getSourceBadge = (source) => {
    const badges = {
      db: { text: 'From your profile', color: '#155724', bg: '#d4edda' },
      llm: { text: 'AI matched', color: '#856404', bg: '#fff3cd' },
      none: { text: 'Not found', color: '#6c757d', bg: '#e2e3e5' }
    }
    return badges[source] || badges.none
  }

  return (
    <form onSubmit={handleSubmit} className="dynamic-form">
      {fields.map(field => {
        const badge = getSourceBadge(field.source)
        return (
          <div key={field.key} className="field-group" style={{marginBottom:'1.5rem', paddingBottom:'1.5rem', borderBottom:'1px solid rgba(255,255,255,0.1)'}}>
            <div className="field-header" style={{display:'flex', justifyContent:'space-between', marginBottom:'0.5rem'}}>
              <label className="field-label" style={{fontWeight:600}}>
                {field.label}
                {field.required && <span className="required" style={{color:'#f87171'}}> *</span>}
              </label>
              <span className="source-badge" style={{
                fontSize:'0.75rem',
                padding:'0.25rem 0.75rem',
                borderRadius:'12px',
                background: badge.bg,
                color: badge.color
              }}>
                {badge.text}
              </span>
            </div>
            
            {field.matched_profile_key && (
              <div className="field-hint" style={{fontSize:'0.75rem', color:'#666', marginBottom:'0.5rem'}}>
                Mapped from: {field.matched_profile_key}
              </div>
            )}
            
            {renderField(field)}
            
          </div>
        )
      })}

      <div className="form-actions review-actions">
        <button 
          type="submit" 
          className="btn btn-primary"
          disabled={submitting}
        >
          {submitting ? 'Confirming...' : 'Confirm & Start Filling →'}
        </button>
      </div>
    </form>
  )
}

export default DynamicReviewForm
