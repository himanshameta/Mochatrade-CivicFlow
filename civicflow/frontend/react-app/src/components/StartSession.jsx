import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { ArrowRight, Bot, Pencil, Lock } from 'lucide-react'

const StartSession = ({ onSessionCreated }) => {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const response = await axios.post('/sessions/start', { url })
      const sessionId = response.data.session_id

      onSessionCreated(sessionId)
      navigate(`/form-review/${sessionId}`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to process form URL')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="start-session">
      <div className="hero">
        <h1>Autofill Any Web Form</h1>
        <p>Enter the form URL and we'll help you fill it automatically</p>
      </div>

      <div className="card">
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="url">Form URL</label>
            <input
              type="url"
              id="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/form"
              required
              disabled={loading}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button 
            type="submit" 
            className="btn btn-primary" 
            disabled={loading || !url}
          >
            {loading ? 'Processing...' : <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>Start Autofill <ArrowRight size={16} /></span>}
          </button>
        </form>
      </div>

      <div className="features">
        <div className="feature">
          <span className="feature-icon"><Bot size={24} /></span>
          <h3>AI-Powered Mapping</h3>
          <p>Automatically matches your profile data to form fields</p>
        </div>
        <div className="feature">
          <span className="feature-icon"><Pencil size={24} /></span>
          <h3>Review Before Submit</h3>
          <p>Always review and edit values before autofill runs</p>
        </div>
        <div className="feature">
          <span className="feature-icon"><Lock size={24} /></span>
          <h3>Secure & Private</h3>
          <p>Your data is encrypted and never stored without permission</p>
        </div>
      </div>
    </div>
  )
}

export default StartSession
