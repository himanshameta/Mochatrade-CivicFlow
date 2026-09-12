import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import { Bot, ArrowLeft, RefreshCw, CheckCircle2, AlertTriangle, ShieldAlert, Sparkles, Terminal } from 'lucide-react'

const ExecutionView = ({ showToast }) => {
  const { sessionId } = useParams()
  const navigate = useNavigate()

  const [status, setStatus] = useState('starting')
  const [error, setError] = useState(null)
  const [pauseScreenshot, setPauseScreenshot] = useState(null)
  const [otpValue, setOtpValue] = useState('')
  const [events, setEvents] = useState([])
  const [currentField, setCurrentField] = useState(null)
  const [filledCount, setFilledCount] = useState(0)
  const [totalFields, setTotalFields] = useState(0)
  const [submittingResume, setSubmittingResume] = useState(false)
  const [applicationId, setApplicationId] = useState(null)

  const pollInterval = useRef(null)
  const wsRef = useRef(null)
  const activityLogEndRef = useRef(null)

  // ── Helper to add activity log entry ──
  const addEvent = (entry) => {
    setEvents(prev => {
      // Avoid duplicate logs if identical timestamp and text
      if (prev.length > 0 && prev[prev.length - 1].text === entry.text) {
        return prev
      }
      return [...prev, { id: Date.now() + Math.random(), ...entry }]
    })
  }

  // Auto-scroll activity log
  useEffect(() => {
    if (activityLogEndRef.current) {
      activityLogEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events])

  // ── Initial session load & polling ──
  useEffect(() => {
    fetchInitialSession()
    connectWebSocket()
    startPolling()

    return () => {
      if (pollInterval.current) clearInterval(pollInterval.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [sessionId])

  const fetchInitialSession = async () => {
    try {
      const res = await axios.get(`/sessions/${sessionId}`)
      const sData = res.data.data
      if (!sData) return

      if (sData.status) setStatus(sData.status)
      if (sData.error) setError(sData.error)
      if (sData.pause_screenshot) setPauseScreenshot(sData.pause_screenshot)

      // Get count of executable fields from pre_filled_values or scraped_form
      if (sData.pre_filled_values) {
        const fieldKeys = Object.keys(sData.pre_filled_values)
        setTotalFields(fieldKeys.length)
      } else if (sData.scraped_form && sData.scraped_form.fields) {
        setTotalFields(sData.scraped_form.fields.length)
      }

      // Add initial milestone logs
      const t = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      setEvents([
        { id: 1, timestamp: t, icon: '✓', text: 'Form structure analyzed', type: 'completed' },
        { id: 2, timestamp: t, icon: '✓', text: 'User information confirmed', type: 'completed' }
      ])
    } catch (err) {
      console.error('[ExecutionView] Initial fetch error:', err)
    }
  }

  // ── WebSocket Connection ──
  const connectWebSocket = () => {
    try {
      const wsUrl = `ws://localhost:8000/ws/${sessionId}`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('[WS] Connected to session:', sessionId)
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

          if (msg.event === 'status_changed') {
            if (msg.status) setStatus(msg.status)
            addEvent({ timestamp, icon: '⚡', text: msg.message || `Status updated to ${msg.status}`, type: 'status' })
          } else if (msg.event === 'field_filling') {
            setCurrentField(msg.label)
            addEvent({ timestamp, icon: '→', text: `Filling ${msg.label}...`, type: 'filling' })
          } else if (msg.event === 'field_filled') {
            setFilledCount(prev => prev + 1)
            setCurrentField(null)
            addEvent({ timestamp, icon: '✓', text: `${msg.label} filled successfully`, type: 'filled' })
          } else if (msg.event === 'navigation') {
            addEvent({ timestamp, icon: '🌐', text: msg.message || 'Opening automated browser...', type: 'nav' })
          } else if (msg.event === 'submitting' || msg.event === 'submission') {
            setStatus('submitting')
            addEvent({ timestamp, icon: '🚀', text: msg.message || 'Submitting form...', type: 'submit' })
          } else if (msg.event === 'captcha_completed') {
            setStatus('running')
            addEvent({ timestamp, icon: '✓', text: 'Human verification completed in browser — resuming automation...', type: 'completed' })
          } else if (msg.event === 'submission_complete') {
            setStatus('completed')
            if (msg.application_id) setApplicationId(msg.application_id)
            addEvent({ timestamp, icon: '✓', text: msg.message || 'Form submitted and verified successfully', type: 'completed' })
          } else if (msg.event === 'interrupted') {
            setStatus('interrupted')
            addEvent({ timestamp, icon: '⚠', text: msg.message || 'Browser window closed by user', type: 'warning' })
          } else if (msg.event === 'captcha_detected') {
            setStatus('paused_captcha')
            if (msg.screenshot_b64) setPauseScreenshot(msg.screenshot_b64)
            addEvent({ timestamp, icon: '⚠', text: 'CAPTCHA detected — manual intervention required', type: 'warning' })
          } else if (msg.event === 'error') {
            setStatus(prev => (prev === 'completed' || prev === 'interrupted' ? prev : 'failed'))
            if (status !== 'completed' && status !== 'interrupted') {
              setError(msg.message)
            }
            addEvent({ timestamp, icon: '✗', text: `Execution error: ${msg.message}`, type: 'error' })
          }
        } catch (err) {
          console.error('[WS] Parse error:', err)
        }
      }

      ws.onerror = (err) => {
        console.warn('[WS] Error:', err)
      }
    } catch (err) {
      console.warn('[WS] Could not connect WebSocket:', err)
    }
  }

  // ── HTTP Polling Fallback ──
  const startPolling = () => {
    if (pollInterval.current) clearInterval(pollInterval.current)

    pollInterval.current = setInterval(async () => {
      try {
        const res = await axios.get(`/sessions/${sessionId}`)
        const sessionData = res.data.data

        if (!sessionData) return
        const currentStatus = sessionData.status

        // Protect terminal completed and interrupted states from being overwritten
        setStatus(prev => {
          if (prev === 'completed' || prev === 'interrupted') {
            return prev
          }
          return currentStatus
        })

        if (currentStatus === 'paused_captcha' || currentStatus === 'paused_otp') {
          if (sessionData.pause_screenshot) {
            setPauseScreenshot(sessionData.pause_screenshot)
          }
        }

        if (currentStatus === 'completed' || currentStatus === 'interrupted' || currentStatus === 'failed') {
          clearInterval(pollInterval.current)
          if (currentStatus === 'failed') {
            setError(sessionData.error || 'Execution failed')
          }
        }
      } catch (err) {
        console.error('[Poll] Execution polling error:', err)
      }
    }, 2000)
  }

  // ── Resume Handlers ──
  const handleResumeCaptcha = async () => {
    setSubmittingResume(true)
    try {
      await axios.post(`/sessions/${sessionId}/resume`, { type: 'captcha' })
      setStatus('running')
      showToast('Resuming execution...', 'info')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to resume')
    } finally {
      setSubmittingResume(false)
    }
  }

  const handleResumeOtp = async () => {
    if (!otpValue.trim()) {
      setError('Please enter OTP')
      return
    }

    setSubmittingResume(true)
    try {
      await axios.post(`/sessions/${sessionId}/resume`, {
        type: 'otp',
        otp: otpValue
      })
      setStatus('running')
      setOtpValue('')
      showToast('OTP submitted, resuming...', 'info')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit OTP')
    } finally {
      setSubmittingResume(false)
    }
  }

  const handleRetryExecution = async () => {
    try {
      setError(null)
      setStatus('running')
      showToast('Retrying execution...', 'info')
      await axios.post(`/sessions/${sessionId}/execute`)
      startPolling()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to restart execution')
      setStatus('failed')
    }
  }

  // ── Stepper State Calculation ──
  // Steps: 1: Analyzed, 2: Confirmed, 3: Prep automation, 4: Browser open, 5: Filling fields, 6: Submitted
  const getStepState = (stepIndex) => {
    if (status === 'failed') {
      if (stepIndex === 3 && status === 'confirmed') return 'failed'
      if (stepIndex === 4 && (status === 'script_ready' || status === 'starting')) return 'failed'
      if (stepIndex >= 5) return 'failed'
      return 'completed'
    }

    if (status === 'interrupted') {
      if (stepIndex <= 5) return 'completed'
      return 'failed'
    }

    if (status === 'completed') return 'completed'

    switch (stepIndex) {
      case 1:
      case 2:
        return 'completed'
      case 3: // Preparing automation
        if (['script_ready', 'running', 'submitting', 'paused_captcha', 'paused_otp'].includes(status)) return 'completed'
        if (status === 'confirmed' || status === 'starting') return 'active'
        return 'pending'
      case 4: // Opening browser
        if (['running', 'submitting', 'paused_captcha', 'paused_otp'].includes(status)) return 'completed'
        if (status === 'script_ready') return 'active'
        return 'pending'
      case 5: // Filling form
        if (['running', 'paused_captcha', 'paused_otp'].includes(status)) return 'active'
        if (['submitting', 'completed'].includes(status)) return 'completed'
        return 'pending'
      case 6: // Final submission
        if (status === 'completed') return 'completed'
        if (status === 'submitting') return 'active'
        return 'pending'
      default:
        return 'pending'
    }
  }

  const statusLabel = {
    confirmed: 'Preparing automation...',
    script_ready: 'Opening automated browser...',
    starting: 'Initializing execution...',
    running: currentField ? `Filling ${currentField}...` : 'Filling form on your behalf...',
    submitting: 'Submitting form to portal...',
    paused_captcha: 'CAPTCHA detected — manual intervention required',
    paused_otp: 'OTP required — enter code below',
    interrupted: 'Browser Window Closed',
    completed: 'Form Submitted Successfully!',
    failed: 'Execution Encountered an Error',
  }[status] || status

  const statusStateClass = {
    running: 'state-running',
    submitting: 'state-running',
    script_ready: 'state-running',
    confirmed: 'state-running',
    completed: 'state-completed',
    interrupted: 'state-paused',
    failed: 'state-failed',
    paused_captcha: 'state-paused',
    paused_otp: 'state-paused',
    starting: 'state-starting',
  }[status] || 'state-starting'

  return (
    <div className="view active">
      <div className="page-container" style={{ maxWidth: '680px' }}>

        {/* ── Page Header ── */}
        <div className="exec-header-hero">
          <h2 className={`exec-status-heading ${statusStateClass}`}>{statusLabel}</h2>
          <p>Your information is being securely applied to the form.</p>
          <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'center' }}>
            <span className={`exec-status-chip ${statusStateClass}`}>
              {(status === 'running' || status === 'submitting' || status === 'confirmed' || status === 'script_ready') && (
                <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--info)', animation: 'pulse 1.5s infinite', marginRight: '0.35rem' }} />
              )}
              {status === 'confirmed' ? 'preparing' : status === 'script_ready' ? 'opening browser' : status}
            </span>
          </div>
        </div>

        {/* ── Progress Stepper ── */}
        <div className="exec-stepper">
          {[
            { index: 1, label: 'Form analyzed' },
            { index: 2, label: 'Information confirmed' },
            { index: 3, label: 'Preparing automation' },
            { index: 4, label: 'Opening browser' },
            { index: 5, label: 'Filling form' },
            { index: 6, label: 'Final submission' },
          ].map(step => {
            const state = getStepState(step.index)
            return (
              <div key={step.index} className={`exec-step-item ${state}`}>
                <div className="exec-step-node">
                  {state === 'completed' ? '✓' : state === 'failed' ? '✗' : step.index}
                </div>
                <span className="exec-step-label">{step.label}</span>
              </div>
            )
          })}
        </div>

        {/* ── Field Progress Card (When running/submitting/script_ready/confirmed/paused) ── */}
        {['running', 'submitting', 'script_ready', 'confirmed', 'paused_captcha', 'paused_otp'].includes(status) && (
          <div className="field-progress-card">
            <div className="field-progress-header">
              <span className="field-progress-title">Form Field Progress</span>
              <span className="field-count-pill">
                {totalFields > 0 ? `${filledCount} of ${totalFields} fields` : `${filledCount} fields filled`}
              </span>
            </div>

            <div className="field-progress-bar">
              <div
                className="field-progress-fill"
                style={{
                  width: totalFields > 0
                    ? `${Math.min(100, Math.max(8, (filledCount / totalFields) * 100))}%`
                    : status === 'running' || status === 'submitting' ? '90%' : '15%'
                }}
              />
            </div>

            {currentField && (
              <div className="current-field-badge">
                <Sparkles size={16} style={{ color: 'var(--accent)' }} />
                <span>Currently filling: <strong>{currentField}</strong></span>
              </div>
            )}
          </div>
        )}

        {/* ── CAPTCHA Intervention Panel ── */}
        {status === 'paused_captcha' && (
          <div className="intervention-panel" style={{ marginTop: '1.5rem' }}>
            <div className="intervention-icon"><ShieldAlert size={20} /></div>
            <h3>CAPTCHA Intervention Required</h3>
            <p>Please solve the CAPTCHA in the automated Playwright browser window, then click continue.</p>

            {pauseScreenshot && (
              <img
                src={pauseScreenshot.startsWith('data:') ? pauseScreenshot : `http://localhost:8000${pauseScreenshot}`}
                alt="CAPTCHA screenshot"
                className="exec-screenshot"
                style={{ maxWidth: '100%', margin: '1rem 0', borderRadius: 'var(--radius-sm)', border: '2px solid var(--border)' }}
              />
            )}

            <button onClick={handleResumeCaptcha} disabled={submittingResume} className="btn btn-primary btn-full">
              {submittingResume ? 'Resuming...' : 'I solved it — continue autofill'}
            </button>
          </div>
        )}

        {/* ── OTP Intervention Panel ── */}
        {status === 'paused_otp' && (
          <div className="intervention-panel" style={{ marginTop: '1.5rem' }}>
            <div className="intervention-icon">📱</div>
            <h3>OTP Required</h3>
            <p>Enter the verification code sent to your phone or email.</p>

            <div className="otp-row">
              <input
                type="text"
                value={otpValue}
                onChange={(e) => setOtpValue(e.target.value)}
                placeholder="000000"
                maxLength={6}
                className="otp-input"
                aria-label="One-time password"
              />
              <button onClick={handleResumeOtp} disabled={submittingResume} className="btn btn-primary">
                {submittingResume ? 'Submitting...' : 'Submit OTP'}
              </button>
            </div>
          </div>
        )}

        {/* ── Live Activity Panel ── */}
        <div className="activity-panel" style={{ marginTop: '1.5rem' }}>
          <div className="activity-panel-header">
            <span className="activity-panel-title">
              <Terminal size={16} /> Live Execution Feed
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--muted-foreground)', fontWeight: 600 }}>
              {events.length} event{events.length === 1 ? '' : 's'}
            </span>
          </div>

          <div className="activity-log-feed">
            {events.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '1rem', color: 'var(--muted-foreground)', fontSize: '0.82rem' }}>
                Waiting for pipeline events...
              </div>
            ) : (
              events.map((ev) => (
                <div key={ev.id} className={`activity-log-item ${ev.type === 'filling' ? 'active-item' : ''}`}>
                  <span className="activity-time">{ev.timestamp}</span>
                  <span style={{ fontWeight: 700 }}>{ev.icon}</span>
                  <span className="activity-text">{ev.text}</span>
                </div>
              ))
            )}
            <div ref={activityLogEndRef} />
          </div>
        </div>

        {/* ── Interrupted Panel ── */}
        {status === 'interrupted' && (
          <div className="exec-error-panel" style={{ marginTop: '1.5rem', borderColor: 'var(--accent)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <AlertTriangle size={22} style={{ color: 'var(--accent)' }} />
              <h3 style={{ margin: 0 }}>Browser Window Closed</h3>
            </div>
            <p style={{ fontSize: '0.88rem', color: 'var(--muted-foreground)', marginBottom: '1.25rem' }}>
              Automation was interrupted before completion because the Playwright browser window was closed.
            </p>
            <div style={{ display: 'flex', gap: '1rem' }}>
              <button onClick={handleRetryExecution} className="btn btn-primary" style={{ flex: 1 }}>
                <RefreshCw size={16} /> Retry Execution
              </button>
              <button onClick={() => navigate('/dashboard')} className="btn btn-outline" style={{ flex: 1 }}>
                <ArrowLeft size={16} /> Return to Dashboard
              </button>
            </div>
          </div>
        )}

        {/* ── Success Completion Panel ── */}
        {status === 'completed' && (
          <div className="exec-completed-panel" style={{ marginTop: '1.5rem' }}>
            <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>
              <CheckCircle2 size={56} style={{ color: '#10b981', margin: '0 auto' }} />
            </div>
            <h3 style={{ textTransform: 'uppercase', letterSpacing: '0.05em', color: '#065f46', fontSize: '1.4rem' }}>✅ APPLICATION SUBMITTED</h3>
            <p style={{ marginTop: '0.35rem', marginBottom: '1rem', color: '#475569' }}>
              Application successfully submitted.
            </p>
            {applicationId && (
              <div style={{ marginBottom: '1.5rem', padding: '0.75rem 1rem', background: '#ecfdf5', border: '2px dashed #6ee7b7', borderRadius: '8px', color: '#065f46', fontFamily: 'monospace', fontSize: '1.1rem', fontWeight: 'bold' }}>
                Application ID: {applicationId}
              </div>
            )}
            <button onClick={() => navigate('/dashboard')} className="btn btn-primary btn-full">
              Return to Dashboard
            </button>
          </div>
        )}

        {/* ── Failure Card Panel ── */}
        {status === 'failed' && (
          <div className="exec-error-panel" style={{ marginTop: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <AlertTriangle size={22} style={{ color: '#EF4444' }} />
              <h3 style={{ margin: 0 }}>Execution Encountered an Error</h3>
            </div>
            <p style={{ fontFamily: 'var(--font-mono)', background: 'var(--muted)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', fontSize: '0.82rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {error || 'Execution failed during Playwright browser automation.'}
            </p>

            <div style={{ display: 'flex', gap: '1rem', marginTop: '1.25rem' }}>
              <button onClick={handleRetryExecution} className="btn btn-primary" style={{ flex: 1 }}>
                <RefreshCw size={16} /> Retry Execution
              </button>
              <button onClick={() => navigate('/dashboard')} className="btn btn-outline" style={{ flex: 1 }}>
                <ArrowLeft size={16} /> Dashboard
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}

export default ExecutionView
