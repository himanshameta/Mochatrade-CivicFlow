import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import { Bot, ArrowLeft } from 'lucide-react'

const ExecutionView = ({ showToast }) => {
  const { sessionId } = useParams()
  const navigate = useNavigate()

  const [status, setStatus] = useState('starting')
  const [error, setError] = useState(null)
  const [pauseScreenshot, setPauseScreenshot] = useState(null)
  const [otpValue, setOtpValue] = useState('')
  const [events, setEvents] = useState([])

  const pollInterval = useRef(null)

  useEffect(() => {
    startPolling()
    return () => {
      if (pollInterval.current) clearInterval(pollInterval.current)
    }
  }, [sessionId])

  const startPolling = () => {
    if (pollInterval.current) clearInterval(pollInterval.current)

    pollInterval.current = setInterval(async () => {
      try {
        const res = await axios.get(`/sessions/${sessionId}`)
        const sessionData = res.data.data

        const currentStatus = sessionData.status
        setStatus(currentStatus)

        if (currentStatus === 'paused_captcha' || currentStatus === 'paused_otp') {
          if (sessionData.pause_screenshot) {
            setPauseScreenshot(sessionData.pause_screenshot)
          }
        }

        if (currentStatus === 'completed' || currentStatus === 'failed') {
          clearInterval(pollInterval.current)
          if (currentStatus === 'failed') {
            setError(sessionData.error || 'Execution failed')
          }
        }
      } catch (err) {
        console.error('Polling error', err)
      }
    }, 2000)
  }

  const handleResumeCaptcha = async () => {
    try {
      await axios.post(`/sessions/${sessionId}/resume`, { type: 'captcha' })
      setStatus('running')
      showToast('Resuming execution...', 'info')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to resume')
    }
  }

  const handleResumeOtp = async () => {
    if (!otpValue.trim()) {
      setError('Please enter OTP')
      return
    }

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
    }
  }

  // Map status to CSS class for heading
  const statusStateClass = {
    running: 'state-running',
    completed: 'state-completed',
    failed: 'state-failed',
    paused_captcha: 'state-paused',
    paused_otp: 'state-paused',
    starting: 'state-starting',
  }[status] || 'state-starting'

  const statusLabel = {
    running: 'Filling form on your behalf...',
    completed: 'Form Submitted Successfully!',
    failed: 'Something went wrong',
    paused_captcha: 'CAPTCHA detected — solve manually',
    paused_otp: 'OTP required — enter below',
    starting: 'Starting automation...',
  }[status] || status

  return (
    <div className="view active">
      <div className="page-container" style={{ maxWidth: '600px' }}>

        {/* ── Status heading ── */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <h2 className={`exec-status-heading ${statusStateClass}`}>{statusLabel}</h2>
          <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'center' }}>
            <span className={`exec-status-chip ${statusStateClass}`}>
              {status === 'running' && <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--info)', animation: 'pulse 1.5s infinite', marginRight: '0.35rem' }} />}
              {status}
            </span>
          </div>
        </div>

        {/* ── CAPTCHA intervention ── */}
        {status === 'paused_captcha' && (
          <div className="intervention-panel">
            <div className="intervention-icon"><Bot size={18} /></div>
            <h3>CAPTCHA Detected</h3>
            <p>Please solve the CAPTCHA in the automated browser window, then click continue.</p>

            {pauseScreenshot && (
              <img
                src={`http://localhost:8000${pauseScreenshot}`}
                alt="CAPTCHA screenshot"
                className="exec-screenshot"
                style={{ maxWidth: '100%', margin: '0.75rem 0' }}
              />
            )}

            <button onClick={handleResumeCaptcha} className="btn btn-primary btn-full">
              I solved it — continue
            </button>
          </div>
        )}

        {/* ── OTP intervention ── */}
        {status === 'paused_otp' && (
          <div className="intervention-panel">
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
              <button onClick={handleResumeOtp} className="btn btn-primary">
                Submit OTP
              </button>
            </div>
          </div>
        )}

        {/* ── Error detail ── */}
        {error && (
          <div className="exec-error-panel">
            <h3>Error Detail</h3>
            <p>{error}</p>
          </div>
        )}

        {/* ── Completed ── */}
        {status === 'completed' && (
          <div className="exec-completed-panel">
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✅</div>
            <h3>All done!</h3>
            <p>Your form has been successfully submitted.</p>
            <button onClick={() => navigate('/dashboard')} className="btn btn-primary">
              Return to Dashboard
            </button>
          </div>
        )}

        {/* ── Failed nav ── */}
        {status === 'failed' && (
          <div style={{ marginTop: '2rem', textAlign: 'center' }}>
            <button onClick={() => navigate('/dashboard')} className="btn btn-outline">
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><ArrowLeft size={16} /> Go to Dashboard</span>
            </button>
          </div>
        )}

        {/* ── Running: live indicator ── */}
        {status === 'running' && (
          <div className="glass-card" style={{ textAlign: 'center', marginTop: '1rem' }}>
            <div className="spinner" style={{ margin: '0 auto 1rem' }}></div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
              Automation is running. This may take a minute.
            </p>
          </div>
        )}

      </div>
    </div>
  )
}

export default ExecutionView
