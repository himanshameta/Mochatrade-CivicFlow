import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

// Debug mode: only show debug info in dev or with ?debug=1
const SHOW_DEBUG = import.meta.env.DEV || new URLSearchParams(window.location.search).get('debug') === '1'

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
    setSearchResults(null)
    
    try {
      // Try enhanced search first, fallback to legacy if needed
      let response
      try {
        response = await axios.post('/search/form/enhanced', {
          service_name: serviceName,
          state: state || null,
          user_url: null
        })
      } catch (enhancedError) {
        console.log('Enhanced search failed, falling back to legacy')
        response = await axios.post('/search/form', {
          service_name: serviceName,
          state: state || null,
          user_url: null
        })
      }

      if (response.data.success) {
        setSearchResults(response.data.data)
        const metadata = response.data.data.search_metadata
        
        // Log only in dev mode
        if (SHOW_DEBUG) {
          console.log('[FormSearch] Full response:', JSON.stringify(response.data.data, null, 2))
          console.log('[FormSearch] Metadata:', metadata)
          console.log('[FormSearch] Debug:', response.data.data.debug)
        }
        
        // Handle enhanced format
        if (metadata?.search_mode === 'enhanced' || metadata?.search_mode === 'enhanced_fixed') {
          const hasDirectForm = metadata?.has_direct_form
          let message = hasDirectForm 
            ? 'Found direct automatable form!' 
            : 'Found guidance resources'
          
          showToast(message, hasDirectForm ? 'success' : 'info')
        } else {
          // Legacy format
          if (response.data.data.direct_form) {
            showToast('Found a direct form!', 'success')
          } else {
            showToast('Loaded guidance resources', 'info')
          }
        }
      }
    } catch (error) {
      console.error('[FormSearch] Search error:', error)
      
      if (error.response) {
        console.error('[FormSearch] Error response:', error.response.data)
        const errorMsg = error.response?.data?.message || error.response?.data?.detail?.message || 'Search failed'
        showToast(errorMsg, 'error')
      } else if (error.request) {
        console.error('[FormSearch] No response received')
        showToast('No response from server - check connection', 'error')
      } else {
        console.error('[FormSearch] Request setup error:', error.message)
        showToast('Search request failed: ' + error.message, 'error')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleSelectUrl = (selectedUrl) => {
    setUrl(selectedUrl)
    setMode('url')
    setSearchResults(null)
  }

  // Helper to get display title with fallback
  const getDisplayTitle = (item) => {
    if (item.display_title) return item.display_title
    if (item.title && item.title !== 'Unknown Page' && item.title !== 'Page') return item.title
    
    // Fallback based on type
    const typeFallbacks = {
      direct_form: 'Direct Application Form',
      official_guidance: 'Official Guidance',
      document_checklist: 'Document Checklist',
      faq: 'Frequently Asked Questions',
      youtube_video: 'Video Guidance'
    }
    
    return typeFallbacks[item.page_type] || 'Related Resource'
  }

  const renderResultItem = (item, idx) => (
    <div key={idx} className="search-result-item" style={{ marginBottom: '12px', padding: '16px', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h4 style={{ margin: '0 0 4px 0', fontSize: '1.1rem' }}>{getDisplayTitle(item)}</h4>
          <p style={{ margin: '0 0 8px 0', fontSize: '0.85rem', color: 'var(--text-tertiary)', wordBreak: 'break-all' }}>{item.url}</p>
          
          <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '12px', backgroundColor: 'var(--bg-card-hover)', color: 'var(--text-secondary)' }}>
              {Math.round(item.confidence * 100)}% Match
            </span>
            {item.official_domain && (
              <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '12px', backgroundColor: '#e6f4ea', color: '#137333' }}>
                Official
              </span>
            )}
          </div>
          
          {/* Show display_reason for users, evidence only in debug mode */}
          {item.display_reason && (
            <p style={{ fontSize: '0.9rem', margin: '4px 0 0 0', color: 'var(--text-secondary)' }}>
              {item.display_reason}
            </p>
          )}
          
          {SHOW_DEBUG && item.evidence && item.evidence.length > 0 && (
             <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: '4px', fontStyle: 'italic' }}>
               Debug: {item.evidence.join(', ')}
             </div>
          )}
        </div>
      </div>
    </div>
  )

  const renderYouTubeVideo = (video, idx) => (
    <div key={idx} className="search-result-item" style={{ marginBottom: '12px', padding: '16px', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', borderLeft: '4px solid #ff0000' }}>
      <div>
        <h4 style={{ margin: '0 0 4px 0', fontSize: '1.1rem' }}>{video.title || 'Video Guidance'}</h4>
        <p style={{ margin: '0 0 8px 0', fontSize: '0.85rem', color: 'var(--text-tertiary)' }}>
          {video.channel && <span>{video.channel} • </span>}
          <a href={video.url} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>Watch on YouTube</a>
        </p>
        
        <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', flexWrap: 'wrap' }}>
          {video.transcript_available && (
            <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '12px', backgroundColor: '#e6f4ea', color: '#137333' }}>
              📝 Transcript Available
            </span>
          )}
        </div>
        
        {video.transcript_summary && (
           <p style={{ fontSize: '0.9rem', margin: '8px 0 0 0', fontStyle: 'italic', color: 'var(--text-secondary)' }}>
             {video.transcript_summary}
           </p>
        )}
        
        {SHOW_DEBUG && video.video_id && (
          <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: '4px' }}>
            Debug: Video ID {video.video_id}
          </div>
        )}
      </div>
    </div>
  )

  return (
    <div className="view active">
      <div className="page-container">
        <div className="page-hero">
          <h2>Find a Form to Automate</h2>
          <p>Paste a direct form URL or describe what you need</p>
        </div>

        <div className="search-mode-toggle-container" style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
          <button 
            className={`btn ${mode === 'describe' ? 'btn-primary' : 'btn-outline'}`}
            style={{ flex: 1 }}
            onClick={() => setMode('describe')}
          >
            Find a Process
          </button>
          <button 
            className={`btn ${mode === 'url' ? 'btn-primary' : 'btn-outline'}`}
            style={{ flex: 1 }}
            onClick={() => setMode('url')}
          >
            Direct Form URL
          </button>
        </div>

        {mode === 'describe' ? (
          <div className="glass-card search-panel">
            <div className="form-group">
              <label>What do you need to apply for?</label>
              <input
                type="text"
                value={serviceName}
                onChange={(e) => setServiceName(e.target.value)}
                placeholder="e.g. Apply for Passport, Driving License..."
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
              {loading ? 'Deep Web Scanning...' : 'Scan Process'}
            </button>

            {searchResults && (
              <div className="search-results-container">
                
                {/* Debug Info Banner - Only in debug mode */}
                {SHOW_DEBUG && searchResults.debug && searchResults.debug.search_id && (
                  <div style={{ 
                    padding: '12px', 
                    backgroundColor: '#f0f0f0', 
                    borderRadius: '8px', 
                    marginBottom: '16px',
                    fontSize: '0.85rem',
                    color: '#666'
                  }}>
                    <strong>🔍 Debug Mode:</strong> Search ID: {searchResults.debug.search_id} | 
                    Raw: {searchResults.debug.raw_candidates_count || 0} | 
                    Classified: {searchResults.debug.classified_candidates_count || 0} | 
                    Dropped: {searchResults.debug.dropped_candidates_count || 0}
                  </div>
                )}
                
                {/* 1. Direct Form Section */}
                <div className="results-section" style={{ marginBottom: '32px' }}>
                  <h3 style={{ borderBottom: '2px solid var(--accent-primary)', paddingBottom: '8px' }}>Direct Form</h3>
                  {searchResults.direct_form ? (
                    <div className="search-result-item primary-result" style={{ padding: '20px', border: '2px solid var(--accent-primary)', borderRadius: 'var(--radius-lg)', backgroundColor: 'var(--bg-card-hover)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ flex: 1 }}>
                          <h4 style={{ margin: '0 0 8px 0', fontSize: '1.2rem', color: 'var(--text-primary)' }}>
                            {searchResults.direct_form.display_title || searchResults.direct_form.title || 'Direct Application Form'}
                          </h4>
                          <p style={{ margin: '0 0 12px 0', fontSize: '0.9rem', color: 'var(--text-tertiary)', wordBreak: 'break-all' }}>
                            {searchResults.direct_form.url}
                          </p>
                          
                          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
                            <span style={{ fontSize: '0.8rem', padding: '4px 10px', borderRadius: '16px', backgroundColor: 'var(--accent-primary)', color: 'white', fontWeight: '500' }}>
                              {Math.round(searchResults.direct_form.confidence * 100)}% Match
                            </span>
                            {searchResults.direct_form.automatable && (
                              <span style={{ fontSize: '0.8rem', padding: '4px 10px', borderRadius: '16px', backgroundColor: '#e6f4ea', color: '#137333', fontWeight: '500' }}>
                                🤖 Automatable
                              </span>
                            )}
                          </div>
                          
                          {/* User-facing reason */}
                          {searchResults.direct_form.display_reason && (
                            <p style={{ fontSize: '0.9rem', margin: '0 0 8px 0', color: 'var(--text-secondary)' }}>
                              {searchResults.direct_form.display_reason}
                            </p>
                          )}
                          
                          {/* Debug evidence - only in debug mode */}
                          {SHOW_DEBUG && searchResults.direct_form.evidence && searchResults.direct_form.evidence.length > 0 && (
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
                              Debug: {searchResults.direct_form.evidence.join(', ')}
                            </div>
                          )}
                        </div>
                        <button 
                          className="btn btn-primary"
                          onClick={() => handleSelectUrl(searchResults.direct_form.url)}
                          style={{ padding: '12px 24px', fontSize: '1rem', whiteSpace: 'nowrap', marginLeft: '16px' }}
                        >
                          Automate Form →
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ padding: '16px', backgroundColor: '#fff3cd', color: '#856404', borderRadius: '8px', border: '1px solid #ffeeba' }}>
                      <strong>No verified direct form found.</strong> Could not locate an automatable form page. Review the official guidance below or continue manually.
                    </div>
                  )}
                </div>

                {/* 4. Process Insights */}
                {searchResults.insights && searchResults.insights.summary && (
                  <div className="insights-panel" style={{ 
                    padding: '24px', 
                    backgroundColor: 'var(--bg-card)', 
                    borderRadius: 'var(--radius-lg)',
                    marginBottom: '32px',
                    borderLeft: '4px solid var(--accent-secondary)',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.05)'
                  }}>
                    <h3 style={{ marginTop: 0, marginBottom: '16px', color: 'var(--text-primary)' }}>Application Insights</h3>
                    
                    <p style={{ lineHeight: '1.6', color: 'var(--text-secondary)' }}>
                      {searchResults.insights.summary}
                    </p>

                    {searchResults.insights.likely_steps?.length > 0 && (
                      <div style={{ marginTop: '20px' }}>
                        <h4 style={{ margin: '0 0 10px 0' }}>Likely Steps:</h4>
                        <ol style={{ margin: 0, paddingLeft: '20px', color: 'var(--text-secondary)' }}>
                          {searchResults.insights.likely_steps.map((step, i) => <li key={i} style={{ marginBottom: '6px' }}>{step}</li>)}
                        </ol>
                      </div>
                    )}

                    {searchResults.insights.likely_required_documents?.length > 0 && (
                      <div style={{ marginTop: '20px' }}>
                        <h4 style={{ margin: '0 0 10px 0' }}>Required Documents:</h4>
                        <ul style={{ margin: 0, paddingLeft: '20px', color: 'var(--text-secondary)' }}>
                          {searchResults.insights.likely_required_documents.map((doc, i) => <li key={i} style={{ marginBottom: '6px' }}>{doc}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* 2. Official Guidance */}
                {((searchResults.official_guidance && searchResults.official_guidance.length > 0) || (searchResults.document_checklists && searchResults.document_checklists.length > 0)) && (
                  <div className="results-section" style={{ marginBottom: '32px' }}>
                    <h3 style={{ borderBottom: '1px solid var(--border-light)', paddingBottom: '8px' }}>Official Guidance</h3>
                    {[...(searchResults.official_guidance || []), ...(searchResults.document_checklists || [])].map((item, i) => renderResultItem(item, i))}
                  </div>
                )}

                {/* 3. Video Guidance */}
                {searchResults.youtube_videos && searchResults.youtube_videos.length > 0 && (
                  <div className="results-section" style={{ marginBottom: '32px' }}>
                    <h3 style={{ borderBottom: '1px solid var(--border-light)', paddingBottom: '8px' }}>Video Guidance</h3>
                    {searchResults.youtube_videos.map((vid, i) => renderYouTubeVideo(vid, i))}
                  </div>
                )}

                {/* Debug Panel - Only in debug mode */}
                {SHOW_DEBUG && searchResults.debug && Object.keys(searchResults.debug).length > 0 && (
                  <details style={{ marginTop: '40px', padding: '16px', backgroundColor: '#1e1e1e', color: '#d4d4d4', borderRadius: '8px' }}>
                    <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>🔍 Debug: Pipeline Diagnostics</summary>
                    <pre style={{ overflowX: 'auto', fontSize: '0.8rem', marginTop: '12px' }}>
                      {JSON.stringify(searchResults.debug, null, 2)}
                    </pre>
                  </details>
                )}

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
                onKeyDown={(e) => e.key === 'Enter' && handleDirectUrl()}
              />
            </div>
            <button 
              className="btn btn-primary" 
              onClick={handleDirectUrl}
              disabled={loading}
              style={{ width: '100%' }}
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
