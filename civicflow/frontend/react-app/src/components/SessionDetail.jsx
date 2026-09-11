import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'

const SessionDetail = ({ showToast }) => {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadSession()
  }, [sessionId])

  const loadSession = async () => {
    try {
      const response = await axios.get(`/sessions/${sessionId}/status`)
      setSession(response.data.data)
    } catch (error) {
      showToast('Failed to load session details', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleContinue = () => {
    if (session.status === 'awaiting_confirmation') {
      navigate(`/form-review/${sessionId}`)
    } else if (session.status === 'confirmed') {
      navigate(`/execution/${sessionId}`)
    } else if (session.status === 'needs_user_input') {
      navigate(`/form-review/${sessionId}`)
    }
  }

  if (loading) return <div className="loading-overlay"><div className="spinner"></div></div>

  if (!session) {
    return (
      <div className="view active">
        <div className="page-container">
          <div className="glass-card">
            <h2>Session Not Found</h2>
            <p>Unable to load session details.</p>
            <button className="btn btn-primary" onClick={() => navigate('/dashboard')}>
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="view active">
      <div className="page-container">
        <div className="page-hero">
          <h2>Session Details</h2>
          <p>View your form automation progress</p>
        </div>

        <div className="glass-card">
          <div className="session-detail-header">
            <div>
              <h3>{session.scraped_form_summary?.total_fields || 0} Fields Detected</h3>
              <p className="session-url">{session.url}</p>
            </div>
            <span className={`status-badge ${session.status}`}>{session.status}</span>
          </div>

          <div className="session-detail-stats">
            <div className="stat-card">
              <div className="stat-label">Status</div>
              <div className="stat-value">{session.status}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Total Fields</div>
              <div className="stat-value">{session.scraped_form_summary?.total_fields || 0}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Mapped Fields</div>
              <div className="stat-value">{session.analyst_summary?.mapped_fields || 0}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Missing</div>
              <div className="stat-value">{session.analyst_summary?.missing_required || 0}</div>
            </div>
          </div>

          {session.missing_fields && session.missing_fields.length > 0 && (
            <div className="missing-fields-panel">
              <h4>⚠ Missing Required Fields</h4>
              <ul>
                {session.missing_fields.map((field, i) => (
                  <li key={i}>{field.key || field.label}</li>
                ))}
              </ul>
            </div>
          )}

          {session.error && (
            <div className="error-panel">
              <h4>❌ Error</h4>
              <p>{session.error}</p>
            </div>
          )}

          <div className="session-detail-actions">
            <button className="btn btn-outline" onClick={() => navigate('/dashboard')}>
              Back to Dashboard
            </button>
            {(session.status === 'awaiting_confirmation' || session.status === 'confirmed' || session.status === 'needs_user_input') && (
              <button className="btn btn-primary" onClick={handleContinue}>
                Continue →
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default SessionDetail
