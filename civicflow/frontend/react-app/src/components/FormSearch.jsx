import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { ArrowRight } from 'lucide-react'

const FormSearch = ({ showToast }) => {
  const [mode, setMode] = useState('url')
  const [url, setUrl] = useState('')
  const [serviceName, setServiceName] = useState('')
  const [state, setState] = useState('')
  const [loading, setLoading] = useState(false)
  const [searchResults, setSearchResults] = useState(null)
  const navigate = useNavigate()

  const handleDirectUrl = async () => {
    if (!url.trim()) {
      showToast('Please enter a URL', 'warning')
      return
    }

    setLoading(true)
    try {
      const response = await axios.post('/start', { url })
      const sessionId = response.data.data.session_id
      showToast('Form analysis started!', 'info')
      navigate(`/form-review/${sessionId}`)
    } catch (error) {
      showToast(error.response?.data?.detail || 'Failed to process URL', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async () => {
    if (!serviceName.trim()) {
      showToast('Please enter a service name', 'warning')
      return
    }

    setLoading(true)
    try {
      const response = await axios.post('/search/form', {
        service_name: serviceName,
        state: state || null,
        user_url: null
      })

      if (response.data.success) {
        setSearchResults(response.data.data)
        if (response.data.data.urls && response.data.data.urls.length > 0) {
          showToast('Found matching forms!', 'success')
        } else {
          showToast('No forms found. Try different keywords.', 'info')
        }
      }
    } catch (error) {
      showToast(error.response?.data?.message || 'Search failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectUrl = (selectedUrl) => {
    setUrl(selectedUrl)
    setMode('url')
    setSearchResults(null)
  }

  return (
    <div className="view active">
      <div className="page-container">
        <div className="page-hero">
          <h2>Find a Form to Autofill</h2>
          <p>Paste a direct form URL or describe what you need</p>
        </div>

        <div className="search-mode-toggle-container" style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
          <button 
            className={`btn ${mode === 'describe' ? 'btn-primary' : 'btn-outline'}`}
            style={{ flex: 1 }}
            onClick={() => setMode('describe')}
          >
            Search For Forms
          </button>
          <button 
            className={`btn ${mode === 'url' ? 'btn-primary' : 'btn-outline'}`}
            style={{ flex: 1 }}
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
                value={serviceName}
                onChange={(e) => setServiceName(e.target.value)}
                placeholder="e.g. Apply for Passport, Job Application..."
              />
            </div>
            <div className="form-group">
              <label>State (Optional)</label>
              <input
                type="text"
                value={state}
                onChange={(e) => setState(e.target.value)}
                placeholder="e.g. Karnataka, Maharashtra"
              />
            </div>
            <button 
              className="btn btn-primary" 
              onClick={handleSearch}
              disabled={loading}
            >
              {loading ? 'Searching...' : 'Search Forms'}
            </button>

            {searchResults && searchResults.urls && searchResults.urls.length > 0 && (
              <div className="search-results">
                <h3>Found Forms:</h3>
                {searchResults.urls.map((urlData, i) => (
                  <div key={i} className="search-result-item">
                    <div>
                      <strong>{urlData.title || 'Form'}</strong>
                      <p>{urlData.url}</p>
                      {urlData.description && <p className="result-desc">{urlData.description}</p>}
                    </div>
                    <button 
                      className="btn btn-sm btn-primary"
                      onClick={() => handleSelectUrl(urlData.url)}
                    >
                      Select
                    </button>
                  </div>
                ))}
              </div>
            )}
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
              {loading ? 'Processing...' : <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>Verify & Continue <ArrowRight size={16} /></span>}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default FormSearch
