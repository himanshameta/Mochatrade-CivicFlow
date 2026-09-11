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

  // ── Inline field update ──
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
          <div className="glass-card exec-error-panel" style={{ textAlign: 'center' }}>
            <h2 className="exec-status-heading state-failed">Pipeline Failed</h2>
            <p style={{ marginTop: '1rem', marginBottom: '2rem' }}>{errorMessage}</p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem' }}>
              <button className="btn btn-outline" onClick={() => navigate('/dashboard')}>← Back to Dashboard</button>
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
        <p className="loading-text">Analyzing form — status: {sessionStatus || 'processing'}</p>
      </div>
    )
  }

  if (debugPayload && !confirmData) {
    return (
      <div className="view active">
        <div className="page-container">
          <div className="glass-card review-warning-panel" style={{ borderColor: 'rgba(252,211,77,0.3)' }}>
            <h2 style={{ color: 'var(--warning)' }}>⚠ Debug: Unexpected Response</h2>
            <pre style={{ background: 'var(--surface-alt)', color: 'var(--text-secondary)', padding: '1rem', borderRadius: 'var(--radius-sm)', overflow: 'auto', maxHeight: '400px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', marginTop: '1rem' }}>
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
            <p style={{ marginTop: '0.5rem', color: 'var(--text-secondary)' }}>Please wait while we prepare the form for review.</p>
            <button className="btn btn-primary" onClick={fetchConfirmData} style={{ marginTop: '1.5rem' }}>Retry Load</button>
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
            <p className="font-mono" style={{ fontSize: '0.82rem' }}>{confirmData.page_title || confirmData.url}</p>
          </div>

          {/* ── Summary stats ── */}
          {summary && (
            <div className="review-stats-row">
              <div className="review-stat-card stat-prefilled">
                <div className="review-stat-number">{summary.prefilled_count}</div>
                <div className="review-stat-label">Pre-filled</div>
              </div>
              <div className={`review-stat-card stat-missing${summary.missing_required_count > 0 ? '' : ' stat-prefilled'}`}>
                <div className="review-stat-number">{summary.missing_required_count}</div>
                <div className="review-stat-label">Missing Required</div>
              </div>
              <div className="review-stat-card stat-optional">
                <div className="review-stat-number">{summary.optional_unfilled_count || 0}</div>
                <div className="review-stat-label">Optional</div>
              </div>
              <div className="review-stat-card stat-total">
                <div className="review-stat-number">{summary.total_fields}</div>
                <div className="review-stat-label">Total Fields</div>
              </div>
            </div>
          )}

          {/* ── Warnings ── */}
          {warnings.length > 0 && (
            <div className="review-warning-panel">
              <h4>⚠ {warnings.length} Warning{warnings.length > 1 ? 's' : ''}</h4>
              <ul>
                {warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}

          {/* ── File requirements ── */}
          {fileRequirements.length > 0 && (
            <div className="file-req-panel">
              <div className="file-req-panel-header">
                <span>📎</span>
                <h4>File Uploads ({fileRequirements.length})</h4>
              </div>

              {fileRequirements.map((fr, i) => {
                const sel = selectedDocs[fr.key]
                return (
                  <div
                    key={i}
                    className={`file-req-item${sel ? ' is-selected' : ''}${fr.required && !sel ? ' is-required' : ''}`}
                  >
                    <div className="file-req-item-header">
                      <span className="file-req-name">
                        {fr.label}
                        {fr.required && <span className="field-required-tag"> *</span>}
                        {fr.accept && <span className="file-req-accept">({fr.accept})</span>}
                      </span>
                      {sel ? (
                        <span className="badge badge-prefilled">✓ Selected</span>
                      ) : fr.required ? (
                        <span className="badge badge-missing">Required</span>
                      ) : (
                        <span className="badge badge-optional">Optional</span>
                      )}
                    </div>

                    {sel ? (
                      <div className="file-req-selected-info">
                        <span className="file-req-selected-name">
                          📄 {sel.display_name || sel.document_id}
                        </span>
                        <button
                          className="btn btn-sm btn-outline"
                          onClick={() => setSelectedDocs(prev => { const n = { ...prev }; delete n[fr.key]; return n })}
                        >
                          Change
                        </button>
                      </div>
                    ) : (
                      <div className="file-req-actions">
                        <button className="btn btn-sm btn-outline" onClick={() => setActiveModal({ type: 'picker', field: fr })}>
                          📂 Choose from My Documents
                          {(fr.matched_saved_documents || []).length > 0 && (
                            <span style={{ marginLeft: '0.35rem', color: 'var(--success)', fontSize: '0.75rem' }}>
                              ({fr.matched_saved_documents.length} match{fr.matched_saved_documents.length > 1 ? 'es' : ''})
                            </span>
                          )}
                        </button>
                        <button className="btn btn-sm btn-primary" onClick={() => setActiveModal({ type: 'upload', field: fr })}>
                          📤 Upload New
                        </button>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* ── File modals ── */}
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

          {/* ── Form fields ── */}
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

            <div className="review-actions" style={{ marginTop: '1rem', justifyContent: 'flex-start' }}>
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
