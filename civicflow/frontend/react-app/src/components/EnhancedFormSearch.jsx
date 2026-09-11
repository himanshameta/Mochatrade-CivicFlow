import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

// CSS for animations
const enhancedStyles = `
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  
  .automation-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  
  .automation-badge.high {
    background: rgba(34, 197, 94, 0.1);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.2);
  }
  
  .automation-badge.medium {
    background: rgba(251, 191, 36, 0.1);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.2);
  }
  
  .automation-badge.low {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.2);
  }
  
  .direct-form-card {
    padding: 20px;
    border: 2px solid var(--accent-primary);
    border-radius: var(--radius-lg);
    background: linear-gradient(135deg, rgba(255, 215, 0, 0.05), rgba(255, 215, 0, 0.02));
    margin-bottom: 24px;
  }
  
  .youtube-badge {
    background: rgba(255, 0, 0, 0.1);
    color: #ff0000;
    border: 1px solid rgba(255, 0, 0, 0.2);
  }
`

// Inject CSS
if (!document.querySelector('#enhanced-form-search-styles')) {
  const styleSheet = document.createElement('style')
  styleSheet.id = 'enhanced-form-search-styles'
  styleSheet.textContent = enhancedStyles
  document.head.appendChild(styleSheet)
}

const EnhancedFormSearch = ({ showToast }) => {
  const [mode, setMode] = useState('url')
  const [url, setUrl] = useState('')
  const [serviceName, setServiceName] = useState('')
  const [state, setState] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingStage, setLoadingStage] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searchMode, setSearchMode] = useState('enhanced')
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
    setLoadingStage('Analyzing query intent...')
    setSearchResults(null)
    
    const stages = [
      'Analyzing query intent...',
      'Retrieving candidate URLs...',
      'Classifying page types...',
      'Selecting best targets...',
      'Enriching with guidance data...',
      'Packaging results...'
    ]
    
    let stageIndex = 0
    const stageInterval = setInterval(() => {
      if (stageIndex < stages.length - 1) {
        stageIndex++
        setLoadingStage(stages[stageIndex])
      }
    }, 8000)
    
    try {
      const endpoint = searchMode === 'enhanced' ? '/search/form/enhanced' : '/search/form'
      const response = await axios.post(endpoint, {
        service_name: serviceName,
        state: state || null,
        user_url: null,
        mode: searchMode
      })

      clearInterval(stageInterval)

      if (response.data.success) {
        setSearchResults(response.data.data)
        const metadata = response.data.data.search_metadata
        
        if (searchMode === 'enhanced') {
          const hasDirectForm = metadata?.has_direct_form
          let message = hasDirectForm 
            ? 'Found direct automatable form!' 
            : 'Found guidance resources - no direct form available'
          
          if (metadata?.youtube_with_transcripts > 0) {
            message += ` (${metadata.youtube_with_transcripts} videos with transcripts)`
          }
          showToast(message, hasDirectForm ? 'success' : 'info')
        } else {
          const hasResults = response.data.data.direct_forms?.length > 0
          showToast(hasResults ? 'Found matching forms!' : 'No results found', hasResults ? 'success' : 'info')
        }
      }
    } catch (error) {
      clearInterval(stageInterval)
      showToast(error.response?.data?.message || 'Search failed', 'error')
    } finally {
      setLoading(false)
      setLoadingStage('')
    }
  }

  const handleSelectUrl = (selectedUrl) => {
    setUrl(selectedUrl)
    setMode('url')
    setSearchResults(null)
  }

  const getAutomationBadge = (readiness) => {
    const badges = {
      high: { text: 'Fully Automatable', icon: '🤖' },
      medium: { text: 'Partially Automatable', icon: '⚡' },
      low: { text: 'Manual Process Required', icon: '👤' },
      unknown: { text: 'Automation Unknown', icon: '❓' }
    }
    
    const badge = badges[readiness] || badges.unknown
    return (
      <span className={`automation-badge ${readiness}`}>
        <span>{badge.icon}</span>
        {badge.text}
      </span>
    )
  }

  const renderDirectFormCard = (directForm) => (
    <div className="direct-form-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
        <div>
          <h3 style={{ margin: '0 0 8px 0', fontSize: '1.3rem', fontWeight: 'bold' }}>
            🎯 Direct Application Form
          </h3>
          <h4 style={{ margin: '0 0 8px 0', fontSize: '1.1rem' }}>{directForm.title}</h4>
          <p style={{ margin: '0 0 12px 0', fontSize: '0.85rem', color: 'var(--text-tertiary)', wordBreak: 'break-all' }}>
            {directForm.url}
          </p>
          
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
            {directForm.automatable && (
              <span className="automation-badge high">
                🤖 Fully Automatable
              </span>
            )}
            <span style={{ 
              fontSize: '0.75rem', 
              padding: '4px 8px', 
              borderRadius: '12px', 
              backgroundColor: 'var(--bg-card-hover)', 
              color: 'var(--text-secondary)' 
            }}>
              Confidence: {Math.round(directForm.confidence * 100)}%
            </span>
          </div>
        </div>
        
        <button 
          className="btn btn-primary"
          onClick={() => handleSelectUrl(directForm.url)}
          style={{ whiteSpace: 'nowrap', marginLeft: '16px', fontSize: '1rem', padding: '12px 20px' }}
        >
          🚀 Automate This Form
        </button>
      </div>
    </div>
  )

  const renderEnhancedResults = () => {
    if (!searchResults) return null

    const { direct_form, official_guidance, document_checklists, youtube_videos, insights } = searchResults

    return (
      <div className="search-results-container">
        {insights && (
          <div style={{ 
            padding: '20px', 
            backgroundColor: 'var(--bg-card)', 
            borderRadius: 'var(--radius-lg)',
            marginBottom: '24px',
            borderLeft: '4px solid var(--accent-primary)'
          }}>
            <h3 style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>💡</span>
              Process Insights
            </h3>
            
            <div style={{ marginBottom: '16px' }}>
              {getAutomationBadge(insights.automation_readiness)}
            </div>
            
            <p style={{ marginBottom: '16px' }}>{insights.summary}</p>
            
            {insights.likely_steps?.length > 0 && (
              <div style={{ marginBottom: '12px' }}>
                <strong>Likely Steps:</strong>
                <ul style={{ margin: '4px 0', paddingLeft: '20px' }}>
                  {insights.likely_steps.slice(0, 5).map((step, idx) => (
                    <li key={idx} style={{ fontSize: '0.9rem', marginBottom: '4px' }}>{step}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {direct_form ? (
          renderDirectFormCard(direct_form)
        ) : (
          <div style={{ 
            padding: '16px', 
            border: '2px dashed var(--border-light)', 
            borderRadius: 'var(--radius-lg)', 
            textAlign: 'center', 
            marginBottom: '24px',
            backgroundColor: 'rgba(239, 68, 68, 0.05)'
          }}>
            <h3 style={{ margin: '0 0 8px 0', color: 'var(--text-secondary)' }}>
              ⚠️ No Direct Form Found
            </h3>
            <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              No verified direct application form detected. Check guidance resources below.
            </p>
          </div>
        )}

        {youtube_videos?.length > 0 && (
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ borderBottom: '1px solid var(--border-light)', paddingBottom: '8px', marginBottom: '16px' }}>
              📺 Video Guidance
            </h3>
            {youtube_videos.map((video, idx) => (
              <div key={idx} style={{ 
                marginBottom: '12px', 
                padding: '16px', 
                border: '1px solid var(--border-light)', 
                borderRadius: 'var(--radius-md)'
              }}>
                <h4 style={{ margin: '0 0 4px 0', fontSize: '1rem' }}>{video.title}</h4>
                <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
                  <span className="youtube-badge">YouTube</span>
                  {video.transcript_available && (
                    <span style={{ 
                      fontSize: '0.75rem', 
                      padding: '2px 6px', 
                      borderRadius: '10px', 
                      backgroundColor: 'rgba(34, 197, 94, 0.1)', 
                      color: '#22c55e'
                    }}>
                      📝 Transcript Available
                    </span>
                  )}
                </div>
                <button 
                  className="btn btn-sm btn-outline"
                  onClick={() => window.open(video.url, '_blank')}
                >
                  ▶️ Watch
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="view active">
      <div className="page-container">
        <div className="page-hero">
          <h2>Find a Form to Autofill</h2>
          <p>Enhanced multi-source search with strict classification</p>
          
          <div style={{ 
            backgroundColor: 'rgba(255, 215, 0, 0.1)', 
            border: '1px solid rgba(255, 215, 0, 0.3)',
            borderRadius: 'var(--radius-md)',
            padding: '12px 16px',
            margin: '16px 0',
            fontSize: '0.9rem'
          }}>
            <strong>🎯 Enhanced Search:</strong> Strict classification separates direct forms from guidance. 
            YouTube videos are never treated as form links.
          </div>
        </div>

        <div className="glass-card" style={{ marginBottom: '16px', padding: '16px' }}>
          <label style={{ fontSize: '0.9rem', marginBottom: '8px', display: 'block' }}>Search Mode:</label>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button 
              className={`mode-btn ${searchMode === 'enhanced' ? 'active' : ''}`}
              onClick={() => setSearchMode('enhanced')}
              style={{ padding: '8px 16px', fontSize: '0.9rem' }}
            >
              🎯 Enhanced
            </button>
            <button 
              className={`mode-btn ${searchMode === 'legacy' ? 'active' : ''}`}
              onClick={() => setSearchMode('legacy')}
              style={{ padding: '8px 16px', fontSize: '0.9rem' }}
            >
              📋 Legacy
            </button>
          </div>
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
                value={serviceName}
                onChange={(e) => setServiceName(e.target.value)}
                placeholder="e.g. Apply for Passport, Job Application..."
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              />
            </div>
            <div className="form-group">
              <label>State (Optional)</label>
              <input
                type="text"
                value={state}
                onChange={(e) => setState(e.target.value)}
                placeholder="e.g. Karnataka, Maharashtra"
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              />
            </div>
            <button 
              className="btn btn-primary" 
              onClick={handleSearch}
              disabled={loading}
              style={{ width: '100%', marginBottom: searchResults ? '24px' : '0' }}
            >
              {loading ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                  <div style={{ 
                    width: '16px', height: '16px', 
                    border: '2px solid transparent', 
                    borderTop: '2px solid white', 
                    borderRadius: '50%', 
                    animation: 'spin 1s linear infinite' 
                  }}></div>
                  {loadingStage || 'Searching...'}
                </div>
              ) : `🔍 Search Forms (${searchMode})`}
            </button>

            {searchMode === 'enhanced' ? renderEnhancedResults() : null}
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
                onKeyDown={(e) => e.key === 'Enter' && handleDirectUrl()}
              />
            </div>
            <button 
              className="btn btn-primary" 
              onClick={handleDirectUrl}
              disabled={loading}
              style={{ width: '100%' }}
            >
              {loading ? 'Processing...' : 'Verify & Continue →'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default EnhancedFormSearch