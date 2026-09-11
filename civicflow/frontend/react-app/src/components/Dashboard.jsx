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

  const greeting = user?.email?.split('@')[0] || 'User'

  return (
    <div className="view active">
      <div className="dashboard-layout">

        {/* ── Hero ── */}
        <div className="page-hero">
          <h2>Welcome back, {greeting}</h2>
          <p>Your private form automation workspace — what would you like to do today?</p>
        </div>

        {/* ── Quick actions ── */}
        <div className="quick-actions">
          <div
            className="quick-card"
            onClick={() => navigate('/form-search')}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && navigate('/form-search')}
            aria-label="Fill a new form"
          >
            <div className="quick-icon">🔍</div>
            <div>
              <div className="quick-title">Fill a New Form</div>
              <div className="quick-desc">Search for any form by URL or name</div>
            </div>
          </div>

          <div
            className="quick-card"
            onClick={() => navigate('/profile-setup')}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && navigate('/profile-setup')}
            aria-label="Update your profile"
          >
            <div className="quick-icon">👤</div>
            <div>
              <div className="quick-title">Update Profile</div>
              <div className="quick-desc">Add or correct your information</div>
            </div>
          </div>

          <div
            className="quick-card"
            onClick={() => navigate('/documents')}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && navigate('/documents')}
            aria-label="Manage your documents"
          >
            <div className="quick-icon">📄</div>
            <div>
              <div className="quick-title">My Documents</div>
              <div className="quick-desc">Manage your secure document vault</div>
            </div>
          </div>
        </div>

        {/* ── Sessions ── */}
        <div className="section-header">
          <h3>Recent Sessions</h3>
          <button className="btn btn-outline btn-sm" onClick={loadSessions} aria-label="Refresh sessions">
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="spinner-center"><div className="spinner"></div></div>
        ) : sessions.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <p>No sessions yet. Start by filling a form!</p>
          </div>
        ) : (
          <div className="sessions-list">
            {sessions.map(session => (
              <div
                key={session.session_id}
                className="session-card"
                onClick={() => navigate(`/session/${session.session_id}`)}
                role="button"
                tabIndex={0}
                onKeyDown={e => e.key === 'Enter' && navigate(`/session/${session.session_id}`)}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="session-form-name">{session.url}</div>
                  <div className="session-url">{new Date(session.created_at).toLocaleString()}</div>
                </div>
                <span className={`status-badge ${session.status}`}>{session.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default Dashboard
