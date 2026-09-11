import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import DynamicReviewForm from './DynamicReviewForm'
import FileUploadModal from './FileUploadModal'
import DocumentPickerModal from './DocumentPickerModal'

const UI_STEPS = {
  IDLE: 'idle',
  RUNNING_PIPELINE: 'running_pipeline',
  AWAITING_CONFIRMATION: 'awaiting_confirmation',
  READY_TO_EXECUTE: 'ready_to_execute',
  EXECUTING: 'executing',
  PAUSED_CAPTCHA: 'paused_captcha',
  COMPLETED: 'completed',
  ERROR: 'error',
}

const FormReview = ({ showToast }) => {
  const { sessionId } = useParams()
  const navigate = useNavigate()

  const [uiStep, setUiStepRaw] = useState(UI_STEPS.RUNNING_PIPELINE)
  const [sessionStatus, setSessionStatus] = useState(null)
  const [confirmData, setConfirmData] = useState(null)
  const [summary, setSummary] = useState(null)
  const [blockers, setBlockers] = useState([])
  const [warnings, setWarnings] = useState([])
  const [missingFields, setMissingFields] = useState([])
  const [fileRequirements, setFileRequirements] = useState([])
  const [errorMessage, setErrorMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [savingInline, setSavingInline] = useState(false)
  const [debugPayload, setDebugPayload] = useState(null)
  const [selectedDocs, setSelectedDocs] = useState({})
  const [activeModal, setActiveModal] = useState(null)

  const pollRef = useRef(null)

  const setUiStep = useCallback((newStep) => {
    setUiStepRaw(prev => {
      console.log(`[FormReview] uiStep: ${prev} → ${newStep}`)
      return newStep
    })
  }, [])

  useEffect(() => {
    console.log('[FormReview] Mounted, starting status polling...')
    startPolling()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [sessionId])

  // ── Polling ──
  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const res = await axios.get(`/sessions/${sessionId}`)
        const { status, error } = res.data.data
        console.log('[Poll] session status:', status)
        setSessionStatus(status)

        if (status === 'failed') {
          clearInterval(pollRef.current)
          setErrorMessage(error || 'Pipeline execution failed.')
          setUiStep(UI_STEPS.ERROR)
          return
        }
        if (['awaiting_confirmation', 'needs_user_input', 'collecting', 'ready', 'confirmed'].includes(status)) {
          clearInterval(pollRef.current)
          setUiStep(UI_STEPS.AWAITING_CONFIRMATION)
          await fetchConfirmData()
          return
        }
        if (status === 'completed') {
          clearInterval(pollRef.current)
          showToast('Form already completed!', 'success')
          navigate(`/execution/${sessionId}`)
          return
        }
        if (status === 'running') {
          setUiStep(UI_STEPS.EXECUTING)
        }
      } catch (err) {
        console.error('[Poll] Error:', err)
      }
    }, 2000)
  }

  // ── Fetch confirm-data ──
  const fetchConfirmData = async () => {
    console.log('[FormReview] Fetching confirm-data...')
    try {
      const response = await axios.get(`/sessions/${sessionId}/confirm-data`)
      const payload = response.data
      if (!payload || !payload.data) {
        setDebugPayload(payload)
        setErrorMessage('Received malformed payload from server')
        setUiStep(UI_STEPS.AWAITING_CONFIRMATION)
        return
      }

      const data = payload.data
      console.log('[ConfirmData] status:', data.status, 'ready:', data.ready_for_execution)
      console.log('[ConfirmData] summary:', JSON.stringify(data.summary))

      // Build fields list
      let fields = []
      if (data.canonical_fields || data.editable_fields) {
        fields = [...(data.canonical_fields || []), ...(data.editable_fields || [])]
        fields = fields.map(f => ({ ...f, key: f.key || f.name }))
      } else if (data.fields) {
        fields = data.fields
      } else if (data.form_fields) {
        fields = data.form_fields.map(f => ({ ...f, key: f.name || f.key || f.label }))
      }

      const schema = {
        session_id: data.session_id || sessionId,
        url: data.url || '',
        page_title: data.page_title || '',
        fields: fields,
        status: data.status || 'awaiting_confirmation',
        ready_for_execution: data.ready_for_execution || false,
        editable_required_fields: (data.editable_required_fields || []).map(f => ({ ...f, key: f.key || f.name })),
        editable_optional_fields: (data.editable_optional_fields || []).map(f => ({ ...f, key: f.key || f.name })),
        canonical_fields: (data.canonical_fields || []).map(f => ({ ...f, key: f.key || f.name })),
      }

      setConfirmData(schema)
      setSummary(data.summary || null)
      setBlockers(data.blockers || [])
      setWarnings(data.warnings || [])
      setMissingFields(data.missing_required_fields || [])
      setFileRequirements(data.file_requirements || [])
      setDebugPayload(null)

      if (data.status === 'error') {
        setErrorMessage(data.blockers?.[0] || 'Backend returned error status')
        setUiStep(UI_STEPS.ERROR)
      } else if (data.ready_for_execution) {
        setUiStep(UI_STEPS.READY_TO_EXECUTE)
      } else {
        setUiStep(UI_STEPS.AWAITING_CONFIRMATION)
      }

      showToast('Form loaded — please review', 'info')
    } catch (error) {
      console.error('[ConfirmData] Fetch error:', error)
      if (error.response?.status === 400) {
        showToast(error.response.data.detail || 'Form not scraped yet', 'warning')
        setTimeout(() => startPolling(), 3000)
      } else {
        setErrorMessage(`Failed to load form data: ${error.message}`)
        setUiStep(UI_STEPS.AWAITING_CONFIRMATION)
      }
    }
  }

  // ── Inline field update (POST /confirm-data) ──
  const handleInlineUpdate = async (fieldValues, persistFlags = {}) => {
    setSavingInline(true)
    try {
      const response = await axios.post(`/sessions/${sessionId}/confirm-data`, {
        field_values: fieldValues,
        persist_to_profile: persistFlags,
      })
      const result = response.data.data
      console.log('[InlineUpdate] Result:', result)

      setMissingFields(result.missing_required_fields || [])
      showToast(result.message || 'Fields updated', 'success')

      // Re-fetch full confirm data to refresh the UI
      await fetchConfirmData()
    } catch (error) {
      console.error('[InlineUpdate] Error:', error)
      showToast('Failed to save field values', 'error')
    } finally {
      setSavingInline(false)
    }
  }

  // ── Retry ──
  const handleRetry = async () => {
    try {
      setUiStep(UI_STEPS.RUNNING_PIPELINE)
      await axios.post(`/sessions/${sessionId}/run`)
      startPolling()
    } catch (err) {
      showToast('Failed to restart analysis', 'error')
      setErrorMessage(err.message || 'Retry failed')
      setUiStep(UI_STEPS.ERROR)
    }
  }

  // ── Confirm & execute ──
  const handleConfirm = async (confirmedData) => {
    const emptyRequired = (confirmData?.editable_required_fields || []).filter(
      f => !confirmedData[f.key]
    )
    if (emptyRequired.length > 0) {
      showToast(`Please fill ${emptyRequired.length} required field(s)`, 'warning')
      return
    }

    setSubmitting(true)
    try {
      const response = await axios.post(`/sessions/${sessionId}/confirm`, {
        confirmed_data: confirmedData
      })
      const result = response.data.data

      if (result.ready_for_execution || result.status === 'confirmed') {
        showToast('Proceeding to autofill...', 'success')
        setUiStep(UI_STEPS.EXECUTING)
        await axios.post(`/sessions/${sessionId}/execute`)
        navigate(`/execution/${sessionId}`)
      } else if (result.missing_required_fields?.length > 0) {
        setMissingFields(result.missing_required_fields)
        setWarnings(result.warnings || [])
        showToast(`${result.missing_required_fields.length} required fields still missing`, 'warning')
        setUiStep(UI_STEPS.AWAITING_CONFIRMATION)
      } else {
        showToast('Data saved', 'success')
        setUiStep(UI_STEPS.AWAITING_CONFIRMATION)
      }
    } catch (error) {
      console.error('[Confirm] Error:', error)
      showToast('Failed to confirm data', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  // ── Render ──

  if (uiStep === UI_STEPS.ERROR) {
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

  if (uiStep === UI_STEPS.RUNNING_PIPELINE || uiStep === UI_STEPS.IDLE) {
    return (
      <div className="loading-overlay">
        <div className="spinner"></div>
        <p>Analyzing form... Status: {sessionStatus || 'processing'}</p>
      </div>
    )
  }

  if (debugPayload && !confirmData) {
    return (
      <div className="view active">
        <div className="page-container">
          <div className="glass-card" style={{ borderColor: '#f59e0b' }}>
            <h2 style={{ color: '#f59e0b' }}>⚠ Debug: Unexpected Response</h2>
            <pre style={{ background: '#1e1e1e', color: '#d4d4d4', padding: '1rem', borderRadius: '8px', overflow: 'auto', maxHeight: '400px', fontSize: '0.8rem' }}>
              {JSON.stringify(debugPayload, null, 2)}
            </pre>
            <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
              <button className="btn btn-outline" onClick={() => navigate('/dashboard')}>Dashboard</button>
              <button className="btn btn-primary" onClick={fetchConfirmData}>Retry</button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!confirmData) {
    return (
      <div className="view active">
        <div className="page-container">
          <div className="glass-card">
            <h2>Loading Form...</h2>
            <p>Please wait while we prepare the form for review.</p>
            <button className="btn btn-primary" onClick={fetchConfirmData} style={{ marginTop: '1rem' }}>Retry Load</button>
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
            <p>{confirmData.page_title || confirmData.url}</p>
          </div>

          {/* Summary bar */}
          {summary && (
            <div style={{
              display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap'
            }}>
              <div style={{ flex: 1, minWidth: '120px', background: '#d1fae5', border: '1px solid #6ee7b7', borderRadius: '8px', padding: '0.75rem 1rem', textAlign: 'center' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#065f46' }}>{summary.prefilled_count}</div>
                <div style={{ fontSize: '0.8rem', color: '#047857' }}>Pre-filled</div>
              </div>
              <div style={{ flex: 1, minWidth: '120px', background: summary.missing_required_count > 0 ? '#fef2f2' : '#d1fae5', border: `1px solid ${summary.missing_required_count > 0 ? '#fecaca' : '#6ee7b7'}`, borderRadius: '8px', padding: '0.75rem 1rem', textAlign: 'center' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: summary.missing_required_count > 0 ? '#dc2626' : '#065f46' }}>{summary.missing_required_count}</div>
                <div style={{ fontSize: '0.8rem', color: summary.missing_required_count > 0 ? '#991b1b' : '#047857' }}>Missing Required</div>
              </div>
              <div style={{ flex: 1, minWidth: '120px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px', padding: '0.75rem 1rem', textAlign: 'center' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#1e40af' }}>{summary.optional_unfilled_count || 0}</div>
                <div style={{ fontSize: '0.8rem', color: '#1d4ed8' }}>Optional</div>
              </div>
              <div style={{ flex: 1, minWidth: '120px', background: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: '8px', padding: '0.75rem 1rem', textAlign: 'center' }}>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#374151' }}>{summary.total_fields}</div>
                <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>Total Fields</div>
              </div>
            </div>
          )}

          {/* Warnings */}
          {warnings.length > 0 && (
            <div style={{ background: '#fffbeb', border: '1px solid #fde68a', padding: '1rem', borderRadius: '8px', marginBottom: '1rem' }}>
              <h4 style={{ color: '#d97706', margin: '0 0 0.5rem 0' }}>⚠ {warnings.length} Warning{warnings.length > 1 ? 's' : ''}</h4>
              <ul style={{ margin: 0, paddingLeft: '1.5rem', color: '#92400e', fontSize: '0.9rem' }}>
                {warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}

          {/* File requirements — interactive */}
          {fileRequirements.length > 0 && (
            <div style={{ background: '#f0f9ff', border: '1px solid #bfdbfe', padding: '1rem', borderRadius: '8px', marginBottom: '1rem' }}>
              <h4 style={{ color: '#1d4ed8', margin: '0 0 0.75rem 0' }}>📎 File Uploads ({fileRequirements.length})</h4>
              {fileRequirements.map((fr, i) => {
                const sel = selectedDocs[fr.key]
                return (
                  <div key={i} style={{ padding: '0.75rem', marginBottom: '0.5rem', borderRadius: '8px', border: sel ? '1px solid #6ee7b7' : fr.required ? '1px solid #fecaca' : '1px solid #e2e8f0', background: sel ? 'rgba(16,185,129,0.06)' : 'transparent' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <span style={{ fontWeight: 600 }}>
                        {fr.label}
                        {fr.required && <span style={{ color: '#ef4444', marginLeft: '0.25rem' }}>*</span>}
                        {fr.accept && <span style={{ color: '#6b7280', fontSize: '0.8rem', marginLeft: '0.5rem' }}>({fr.accept})</span>}
                      </span>
                      {sel ? (
                        <span style={{ padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600, background: '#d1fae5', color: '#065f46' }}>✓ Selected</span>
                      ) : fr.required ? (
                        <span style={{ padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600, background: '#fee2e2', color: '#991b1b' }}>Required</span>
                      ) : (
                        <span style={{ padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600, background: '#e2e3e5', color: '#6c757d' }}>Optional</span>
                      )}
                    </div>

                    {sel ? (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.85rem', color: '#047857' }}>📄 {sel.display_name || sel.document_id}</span>
                        <button className="btn btn-sm btn-outline" onClick={() => setSelectedDocs(prev => { const n = { ...prev }; delete n[fr.key]; return n })}>Change</button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <button className="btn btn-sm btn-outline" onClick={() => setActiveModal({ type: 'picker', field: fr })}>
                          📂 Choose from My Documents
                          {(fr.matched_saved_documents || []).length > 0 && <span style={{ marginLeft: '0.25rem', color: '#10b981' }}>({fr.matched_saved_documents.length} match{fr.matched_saved_documents.length > 1 ? 'es' : ''})</span>}
                        </button>
                        <button className="btn btn-sm btn-primary" onClick={() => setActiveModal({ type: 'upload', field: fr })}>📤 Upload New</button>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* File modals */}
          {activeModal?.type === 'upload' && (
            <FileUploadModal
              sessionId={sessionId}
              fieldName={activeModal.field.key}
              fieldLabel={activeModal.field.label}
              accept={activeModal.field.accept}
              onClose={() => setActiveModal(null)}
              onUploaded={(fieldName, docId) => {
                setSelectedDocs(prev => ({ ...prev, [fieldName]: { document_id: docId, display_name: 'Uploaded file' } }))
                fetchConfirmData()
              }}
              showToast={showToast}
            />
          )}
          {activeModal?.type === 'picker' && (
            <DocumentPickerModal
              sessionId={sessionId}
              fieldName={activeModal.field.key}
              fieldLabel={activeModal.field.label}
              accept={activeModal.field.accept}
              suggestedDocs={activeModal.field.matched_saved_documents || []}
              onClose={() => setActiveModal(null)}
              onSelected={(fieldName, docId, docName) => {
                setSelectedDocs(prev => ({ ...prev, [fieldName]: { document_id: docId, display_name: docName } }))
                fetchConfirmData()
              }}
              showToast={showToast}
            />
          )}

          {/* Form fields */}
          <div className="glass-card">
            <DynamicReviewForm
              fields={confirmData.fields}
              editableRequired={confirmData.editable_required_fields || []}
              editableOptional={confirmData.editable_optional_fields || []}
              canonicalFields={confirmData.canonical_fields || []}
              onConfirm={handleConfirm}
              onInlineUpdate={handleInlineUpdate}
              submitting={submitting}
              savingInline={savingInline}
              hasBlockers={blockers.length > 0}
              readyForExecution={confirmData.ready_for_execution}
            />

            <div className="review-actions" style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-start' }}>
              <button type="button" className="btn btn-outline" onClick={() => navigate('/dashboard')} disabled={submitting}>← Cancel</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default FormReview
