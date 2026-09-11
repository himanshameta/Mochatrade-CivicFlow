import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import DynamicReviewForm from './DynamicReviewForm'

const FormReview = ({ showToast }) => {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [schema, setSchema] = useState(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [sessionStatus, setSessionStatus] = useState(null)
  const [missingFields, setMissingFields] = useState([])

  const [hasFailed, setHasFailed] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    pollSessionStatus()
  }, [sessionId])

  const pollSessionStatus = async () => {
    console.log('[FormReview] Starting status polling...')
    
    const interval = setInterval(async () => {
      try {
        const res = await axios.get(`/sessions/${sessionId}`)
        const { status, error } = res.data.data
        
        console.log('[Poll] session status:', status)
        setSessionStatus(status)

        if (status === 'failed') {
          clearInterval(interval)
          setHasFailed(true)
          setErrorMessage(error || 'Pipeline execution failed.')
          setLoading(false)
          return
        }

        if (
          status === 'awaiting_confirmation' ||
          status === 'needs_user_input' ||
          status === 'collecting' ||
          status === 'ready'
        ) {
          clearInterval(interval)
          await loadSchema()
        }

        if (status === 'completed') {
          clearInterval(interval)
          showToast('Form already completed!', 'success')
          navigate(`/execution/${sessionId}`)
        }
      } catch (err) {
        console.error('[Poll] Error:', err)
      }
    }, 2000)

    return () => clearInterval(interval)
  }

  const handleRetry = async () => {
    try {
      setHasFailed(false)
      setLoading(true)
      await axios.post(`/sessions/${sessionId}/run`)
      pollSessionStatus()
    } catch (err) {
      showToast('Failed to restart analysis', 'error')
      setHasFailed(true)
      setLoading(false)
    }
  }

  const loadSchema = async () => {
    try {
      console.log('[FormReview] Loading confirm-data...')
      const response = await axios.get(`/sessions/${sessionId}/confirm-data`)
      const data = response.data.data
      
      console.log('[ConfirmData] form_schema fields:', data.fields.length)
      
      setSchema(data)
      setMissingFields(data.missing_required_fields || [])
      
      showToast('Form loaded - please review', 'info')
    } catch (error) {
      if (error.response?.status === 400) {
        showToast(error.response.data.detail || 'Form not scraped yet', 'warning')
        setTimeout(() => pollSessionStatus(), 3000)
      } else {
        showToast('Failed to load form data', 'error')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = async (confirmedData) => {
    const emptyRequired = schema.fields.filter(f => f.required && !confirmedData[f.key])
    if (emptyRequired.length > 0) {
      showToast(`Please fill ${emptyRequired.length} required field(s)`, 'warning')
      return
    }
    
    setSubmitting(true)
    console.log('[Confirm] confirmed keys:', Object.keys(confirmedData))

    try {
      const response = await axios.post(`/sessions/${sessionId}/confirm`, {
        confirmed_data: confirmedData
      })
      
      const newStatus = response.data.data.status
      
      if (newStatus === 'confirmed') {
        showToast('Proceeding to autofill...', 'success')
        
        // Trigger execution
        await axios.post(`/sessions/${sessionId}/execute`)
        
        navigate(`/execution/${sessionId}`)
      } else if (newStatus === 'awaiting_confirmation') {
        const stillMissing = response.data.data.missing_required_fields || []
        setMissingFields(stillMissing)
        showToast(`${stillMissing.length} required fields still missing`, 'warning')
      }
    } catch (error) {
      showToast('Failed to confirm data', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  if (hasFailed) {
    return (
      <div className="view active">
        <div className="page-container">
          <div className="glass-card" style={{ textAlign: 'center', borderColor: '#f87171' }}>
            <h2 style={{ color: '#ef4444' }}>Pipeline Failed</h2>
            <p style={{ marginTop: '1rem', color: '#f87171' }}>{errorMessage}</p>
            <div style={{ marginTop: '2rem', display: 'flex', justifyContent: 'center', gap: '1rem' }}>
              <button className="btn btn-outline" onClick={() => navigate('/dashboard')}>Back to Dashboard</button>
              <button className="btn btn-primary" onClick={handleRetry}>Retry Analysis</button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="loading-overlay">
        <div className="spinner"></div>
        <p>Analyzing form... Status: {sessionStatus || 'processing'}</p>
      </div>
    )
  }

  if (!schema) {
    return (
      <div className="view active">
        <div className="page-container">
          <div className="glass-card">
            <h2>Loading Form...</h2>
            <p>Please wait while we analyze the form.</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="view active">
      <div className="form-review-layout">
        <div className="form-review-main">
          <div className="page-hero">
            <h2>Review Before Filing</h2>
            <p>{schema.page_title || schema.url}</p>
          </div>

          {missingFields.length > 0 && (
            <div style={{background:'#fff3cd', padding:'1rem', borderRadius:'8px', marginBottom:'1rem'}}>
              ⚠ {missingFields.length} required field(s) missing - please fill them before proceeding
            </div>
          )}

          <div className="glass-card">
            <DynamicReviewForm 
              fields={schema.fields} 
              onConfirm={handleConfirm}
              submitting={submitting} 
            />
            
            <div className="review-actions" style={{marginTop:'1rem', display:'flex', justifyContent:'flex-start'}}>
              <button type="button" className="btn btn-outline" onClick={() => navigate('/dashboard')} disabled={submitting}>
                ← Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default FormReview
