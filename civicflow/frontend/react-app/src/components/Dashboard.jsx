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
            <h2>Welcome back, {user?.email?.split('@')[0] || 'User'} 👋</h2>
            <p>What would you like to do today?</p>
          </div>

          <div className="quick-actions">
            <div className="quick-card glass-card" onClick={() => navigate('/form-search')}>
              <div className="quick-icon">🔍</div>
              <div>
                <div className="quick-title">Fill a New Form</div>
                <div className="quick-desc">Search for any form</div>
              </div>
            </div>
            <div className="quick-card glass-card" onClick={() => navigate('/profile-setup')}>
              <div className="quick-icon">👤</div>
              <div>
                <div className="quick-title">Update Profile</div>
                <div className="quick-desc">Add or correct your information</div>
              </div>
            </div>
            <div className="quick-card glass-card" onClick={() => navigate('/documents')}>
              <div className="quick-icon">📄</div>
              <div>
                <div className="quick-title">My Documents</div>
                <div className="quick-desc">Manage uploaded documents</div>
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
    </div>
  )
}

export default Dashboard
