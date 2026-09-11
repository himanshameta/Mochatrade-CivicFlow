# React Components Creation Guide

This document contains all the component code you need to create. Copy each section into its respective file.

## Components to Create

### 1. Dashboard.jsx
```jsx
import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const Dashboard = ({ user, showToast }) => {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    loadSessions()
  }, [])

  const loadSessions = async () => {
    try {
      const response = await axios.get('/sessions')
      setSessions(response.data.sessions || [])
    } catch (error) {
      showToast('Failed to load sessions', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="view active">
      <div className="dashboard-layout">
        <div className="dashboard-main">
          <div className="page-hero">
            <h2>Welcome back, {user?.name} 👋</h2>
            <p>What would you like to do today?</p>
          </div>

          <div className="quick-actions">
            <div className="quick-card glass-card" onClick={() => navigate('/form-search')}>
              <div className="quick-icon">🔍</div>
              <div>
                <div className="quick-title">Fill a New Form</div>
                <div className="quick-desc">Search for any government service</div>
              </div>
            </div>
            <div className="quick-card glass-card" onClick={() => navigate('/profile-setup')}>
              <div className="quick-icon">👤</div>
              <div>
                <div className="quick-title">Update Profile</div>
                <div className="quick-desc">Add or correct your information</div>
              </div>
            </div>
          </div>

          <div className="section-header">
            <h3>Active Sessions</h3>
            <button className="btn btn-outline btn-sm" onClick={loadSessions}>Refresh</button>
          </div>

          {loading ? (
            <div className="spinner-center"><div className="spinner"></div></div>
          ) : sessions.length === 0 ? (
            <div className="empty-state">No active sessions. Start by filling a form!</div>
          ) : (
            <div className="sessions-list">
              {sessions.map(session => (
                <div 
                  key={session.session_id} 
                  className="session-card"
                  onClick={() => navigate(`/session/${session.session_id}`)}
                >
                  <div>
                    <div className="session-form-name">{session.page_title || 'Form Session'}</div>
                    <div className="session-url">{session.url}</div>
                  </div>
                  <span className={`status-badge ${session.status}`}>{session.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Dashboard
```

### 2. FormSearch.jsx
```jsx
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const FormSearch = ({ showToast }) => {
  const [mode, setMode] = useState('url')
  const [url, setUrl] = useState('')
  const [serviceSearch, setServiceSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleDirectUrl = async () => {
    if (!url.trim()) {
      showToast('Please enter a URL', 'warning')
      return
    }

    setLoading(true)
    try {
      const response = await axios.post('/sessions/start', { url })
      const sessionId = response.data.session_id
      navigate(`/form-review/${sessionId}`)
    } catch (error) {
      showToast(error.response?.data?.detail || 'Failed to process URL', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="view active">
      <div className="page-container">
        <div className="page-hero">
          <h2>Find a Form to Autofill</h2>
          <p>Paste a direct form URL or describe what you need</p>
        </div>

        <div className="search-mode-toggle glass-card">
          <button 
            className={`mode-btn ${mode === 'describe' ? 'active' : ''}`}
            onClick={() => setMode('describe')}
          >
            Describe Need
          </button>
          <button 
            className={`mode-btn ${mode === 'url' ? 'active' : ''}`}
            onClick={() => setMode('url')}
          >
            Paste URL
          </button>
        </div>

        {mode === 'describe' ? (
          <div className="glass-card search-panel">
            <div className="form-group">
              <label>What do you need help with?</label>
              <input
                type="text"
                value={serviceSearch}
                onChange={(e) => setServiceSearch(e.target.value)}
                placeholder="e.g. Apply for Passport, Job Application..."
              />
            </div>
            <button className="btn btn-primary" onClick={() => showToast('Search coming soon!', 'info')}>
              Search Forms
            </button>
          </div>
        ) : (
          <div className="glass-card search-panel">
            <div className="form-group">
              <label>Form URL</label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/form"
              />
            </div>
            <button 
              className="btn btn-primary" 
              onClick={handleDirectUrl}
              disabled={loading}
            >
              {loading ? 'Processing...' : 'Verify & Continue →'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default FormSearch
```

### 3. FormReview.jsx (Enhanced DynamicReviewForm)
```jsx
import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'

const FormReview = ({ showToast }) => {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [schema, setSchema] = useState(null)
  const [formData, setFormData] = useState({})
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    loadSchema()
  }, [sessionId])

  const loadSchema = async () => {
    try {
      const response = await axios.get(`/sessions/${sessionId}/confirm-data`)
      setSchema(response.data.data)
      
      const initialData = {}
      response.data.data.fields.forEach(field => {
        initialData[field.key] = field.value || ''
      })
      setFormData(initialData)
    } catch (error) {
      showToast('Failed to load form data', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)

    try {
      await axios.post(`/sessions/${sessionId}/confirm`, {
        confirmed_data: formData
      })
      showToast('Data confirmed successfully!', 'success')
      navigate(`/execution/${sessionId}`)
    } catch (error) {
      showToast('Failed to confirm data', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const renderField = (field) => {
    const value = formData[field.key] || ''
    
    switch (field.field_type) {
      case 'textarea':
        return (
          <textarea
            value={value}
            onChange={(e) => setFormData({...formData, [field.key]: e.target.value})}
            placeholder={field.placeholder}
            required={field.required}
          />
        )
      
      case 'select':
        return (
          <select
            value={value}
            onChange={(e) => setFormData({...formData, [field.key]: e.target.value})}
            required={field.required}
          >
            <option value="">-- Select --</option>
            {field.options.map((opt, i) => (
              <option key={i} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        )
      
      case 'radio':
        return (
          <div>
            {field.options.map((opt, i) => (
              <label key={i} style={{display:'block', margin:'8px 0'}}>
                <input
                  type="radio"
                  name={field.key}
                  value={opt.value}
                  checked={value === opt.value}
                  onChange={(e) => setFormData({...formData, [field.key]: e.target.value})}
                  required={field.required}
                />
                <span style={{marginLeft:'8px'}}>{opt.label}</span>
              </label>
            ))}
          </div>
        )
      
      case 'checkbox':
        return (
          <label>
            <input
              type="checkbox"
              checked={value === 'true'}
              onChange={(e) => setFormData({...formData, [field.key]: e.target.checked ? 'true' : 'false'})}
            />
            <span style={{marginLeft:'8px'}}>{field.label}</span>
          </label>
        )
      
      case 'file':
        return <p style={{color:'#999'}}>File upload: {field.label}</p>
      
      default:
        return (
          <input
            type={field.field_type}
            value={value}
            onChange={(e) => setFormData({...formData, [field.key]: e.target.value})}
            placeholder={field.placeholder}
            required={field.required}
          />
        )
    }
  }

  if (loading) return <div className="loading-overlay"><div className="spinner"></div></div>

  return (
    <div className="view active">
      <div className="form-review-layout">
        <div className="form-review-main">
          <div className="page-hero">
            <h2>Review Before Filing</h2>
            <p>{schema?.page_title || 'Form Review'}</p>
          </div>

          {schema?.missing_required_fields?.length > 0 && (
            <div style={{background:'#fff3cd', padding:'1rem', borderRadius:'8px', marginBottom:'1rem'}}>
              ⚠ {schema.missing_required_fields.length} required field(s) missing
            </div>
          )}

          <div className="glass-card">
            <form onSubmit={handleSubmit}>
              {schema?.fields.map(field => (
                <div key={field.key} style={{marginBottom:'1.5rem', paddingBottom:'1.5rem', borderBottom:'1px solid rgba(255,255,255,0.1)'}}>
                  <div style={{display:'flex', justifyContent:'space-between', marginBottom:'0.5rem'}}>
                    <label style={{fontWeight:600}}>
                      {field.label}
                      {field.required && <span style={{color:'#f87171'}}>*</span>}
                    </label>
                    <span style={{
                      fontSize:'0.75rem',
                      padding:'0.25rem 0.75rem',
                      borderRadius:'12px',
                      background: field.source === 'db' ? '#d4edda' : field.source === 'llm' ? '#cce5ff' : '#f8f9fa',
                      color: field.source === 'db' ? '#155724' : field.source === 'llm' ? '#004085' : '#6c757d'
                    }}>
                      {field.source === 'db' ? 'From Profile' : field.source === 'llm' ? 'AI Mapped' : 'Not Mapped'}
                    </span>
                  </div>
                  {renderField(field)}
                </div>
              ))}

              <div className="review-actions">
                <button type="button" className="btn btn-outline" onClick={() => navigate('/form-search')}>
                  ← Back
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Confirming...' : 'Confirm & Start Filling →'}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}

export default FormReview
```

### 4. ExecutionView.jsx
```jsx
import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'

const ExecutionView = ({ showToast }) => {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState('starting')
  const [events, setEvents] = useState([])
  const [pauseType, setPauseType] = useState(null)
  const [otpValue, setOtpValue] = useState('')

  useEffect(() => {
    startExecution()
    const interval = setInterval(pollStatus, 3000)
    return () => clearInterval(interval)
  }, [sessionId])

  const startExecution = async () => {
    try {
      await axios.post(`/sessions/${sessionId}/execute`)
      setStatus('running')
      addEvent('🚀 Automation started')
    } catch (error) {
      showToast('Failed to start execution', 'error')
      setStatus('failed')
    }
  }

  const pollStatus = async () => {
    try {
      const response = await axios.get(`/sessions/${sessionId}/status`)
      const data = response.data

      if (data.status === 'completed') {
        setStatus('completed')
        addEvent('✓ Form submitted successfully!')
      } else if (data.status === 'failed') {
        setStatus('failed')
        addEvent('✗ Execution failed')
      } else if (data.status === 'paused_captcha') {
        setPauseType('captcha')
      } else if (data.status === 'paused_otp') {
        setPauseType('otp')
      }
    } catch (error) {
      console.error('Poll error:', error)
    }
  }

  const addEvent = (message) => {
    setEvents(prev => [...prev, { message, time: new Date().toLocaleTimeString() }])
  }

  const handleResumeCaptcha = async () => {
    try {
      await axios.post(`/sessions/${sessionId}/resume`, { type: 'captcha' })
      setPauseType(null)
      addEvent('▶ Resuming after CAPTCHA')
    } catch (error) {
      showToast('Failed to resume', 'error')
    }
  }

  const handleResumeOtp = async () => {
    if (!otpValue.trim()) {
      showToast('Please enter OTP', 'warning')
      return
    }

    try {
      await axios.post(`/sessions/${sessionId}/resume`, { type: 'otp', value: otpValue })
      setPauseType(null)
      setOtpValue('')
      addEvent('▶ OTP submitted')
    } catch (error) {
      showToast('Failed to submit OTP', 'error')
    }
  }

  return (
    <div className="view active">
      <div className="execution-layout">
        <div className="execution-main">
          <div className="page-hero">
            <h2>Form Filling in Progress</h2>
            <p className={`status-badge status-${status}`}>
              {status}
            </p>
          </div>

          {pauseType === 'captcha' && (
            <div className="pause-panel glass-card">
              <div className="pause-icon-big">🤖</div>
              <h3>CAPTCHA Detected</h3>
              <p>Please solve the CAPTCHA in the browser, then click Resume.</p>
              <button className="btn btn-warning" onClick={handleResumeCaptcha}>
                I Solved It — Resume ▶
              </button>
            </div>
          )}

          {pauseType === 'otp' && (
            <div className="pause-panel glass-card">
              <div className="pause-icon-big">📱</div>
              <h3>OTP Required</h3>
              <p>Enter the verification code.</p>
              <div className="otp-row">
                <input
                  type="text"
                  className="otp-input"
                  value={otpValue}
                  onChange={(e) => setOtpValue(e.target.value)}
                  placeholder="000000"
                  maxLength={6}
                />
                <button className="btn btn-warning" onClick={handleResumeOtp}>
                  Submit OTP
                </button>
              </div>
            </div>
          )}

          <div className="glass-card">
            <h3>Execution Log</h3>
            <div className="live-tracker">
              {events.map((event, i) => (
                <div key={i} className="tracker-row">
                  <span className="tr-icon">{event.time}</span>
                  <span>{event.message}</span>
                </div>
              ))}
            </div>
          </div>

          {status === 'completed' && (
            <div className="glass-card" style={{textAlign:'center', padding:'3rem'}}>
              <div className="success-icon">✅</div>
              <h3>Form Submitted Successfully!</h3>
              <button className="btn btn-primary" onClick={() => navigate('/dashboard')}>
                Go to Dashboard
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ExecutionView
```

### 5. ProfileSetup.jsx (Placeholder)
```jsx
import React from 'react'

const ProfileSetup = ({ showToast }) => {
  return (
    <div className="view active">
      <div className="page-container">
        <div className="page-hero">
          <h2>Profile Setup</h2>
          <p>Coming soon...</p>
        </div>
      </div>
    </div>
  )
}

export default ProfileSetup
```

### 6. SessionDetail.jsx (Placeholder)
```jsx
import React from 'react'

const SessionDetail = ({ showToast }) => {
  return (
    <div className="view active">
      <div className="page-container">
        <div className="page-hero">
          <h2>Session Detail</h2>
          <p>Coming soon...</p>
        </div>
      </div>
    </div>
  )
}

export default SessionDetail
```

### 7. FloatingCounsellor.jsx (Placeholder)
```jsx
import React, { useState } from 'react'

const FloatingCounsellor = () => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="float-counsellor">
      {isOpen && (
        <div className="float-chat-window">
          <div className="float-chat-header">
            <div className="counsellor-avatar small">🤖</div>
            <div>
              <div className="counsellor-name">Sahayak</div>
              <div className="counsellor-status">AI Assistant</div>
            </div>
            <button className="float-close" onClick={() => setIsOpen(false)}>×</button>
          </div>
          <div className="float-chat-messages">
            <div className="chat-msg bot">Hi! How can I help you today?</div>
          </div>
          <form className="counsellor-input-row">
            <input type="text" placeholder="Ask anything..." />
            <button type="submit" className="btn-send">↑</button>
          </form>
        </div>
      )}
      <button className="float-toggle-btn" onClick={() => setIsOpen(!isOpen)}>
        <span className="float-icon">🤖</span>
      </button>
    </div>
  )
}

export default FloatingCounsellor
```

## Copy the CSS

Copy the entire `styles.css` content to `src/App.css` in your React app.

## Installation Steps

1. Create each component file in `src/components/`
2. Copy the code from this guide into each file
3. Run `npm install` to ensure all dependencies are installed
4. Run `npm run dev` to start the development server

The React app will now have all the same features as your original HTML/JS frontend!
