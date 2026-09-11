import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { FileText } from 'lucide-react'

const CATEGORIES = [
  { value: 'identity', label: 'Identity (Aadhaar, PAN, Passport, etc.)' },
  { value: 'address_proof', label: 'Address Proof' },
  { value: 'education', label: 'Education (Marksheet, Degree)' },
  { value: 'certificate', label: 'Certificate' },
  { value: 'photo', label: 'Photo / Photograph' },
  { value: 'resume', label: 'Resume / CV' },
  { value: 'financial', label: 'Financial (ITR, Salary Slip)' },
  { value: 'medical', label: 'Medical' },
  { value: 'other', label: 'Other' },
]

const DocumentUpload = ({ user, showToast }) => {
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [displayName, setDisplayName] = useState('')
  const [category, setCategory] = useState('')
  const [subcategory, setSubcategory] = useState('')
  const [tags, setTags] = useState('')
  const [uploading, setUploading] = useState(false)

  // OCR Confirm Modal states
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [detectedFields, setDetectedFields] = useState({})
  const [docId, setDocId] = useState('')

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      if (selectedFile.size > 10 * 1024 * 1024) {
        showToast('File size must be less than 10MB', 'error')
        return
      }
      setFile(selectedFile)
      if (!displayName) setDisplayName(selectedFile.name.replace(/\.[^.]+$/, ''))
    }
  }

  const handleUpload = async () => {
    if (!file || !displayName.trim() || !category) {
      showToast('Please fill in file, display name, and category', 'warning')
      return
    }

    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    formData.append('display_name', displayName.trim())
    formData.append('category', category)
    if (subcategory.trim()) formData.append('subcategory', subcategory.trim())
    if (tags.trim()) formData.append('tags', tags.trim())

    try {
      const res = await axios.post('/documents/vault/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      
      const resData = res.data.data
      const extracted = resData.extracted_fields || {}
      
      if (Object.keys(extracted).length > 0) {
        setDetectedFields(extracted)
        setDocId(resData.document.document_id)
        setShowConfirmModal(true)
      } else {
        showToast('Document uploaded to vault!', 'success')
        navigate('/documents')
      }
    } catch (error) {
      showToast(error.response?.data?.detail || 'Failed to upload document', 'error')
    } finally {
      setUploading(false)
    }
  }

  const handleConfirmSave = async () => {
    try {
      await axios.post(`/documents/confirm/${docId}`, {
        corrected_fields: detectedFields
      })
      showToast('Document confirmed and saved to profile!', 'success')
      setShowConfirmModal(false)
      navigate('/documents')
    } catch (error) {
      showToast(error.response?.data?.detail || 'Failed to save fields', 'error')
    }
  }

  return (
    <div className="view active">
      <div className="page-container">
        <div className="page-hero">
          <h2>Upload Document</h2>
          <p>Store documents locally for automatic form filling</p>
        </div>

        <div className="glass-card">
          <div className="upload-panel">
            <div className="form-group">
              <label>Display Name *</label>
              <input type="text" value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="e.g. My Resume 2026, Aadhaar Card" />
            </div>

            <div className="form-group">
              <label>Category *</label>
              <select value={category} onChange={e => setCategory(e.target.value)} required>
                <option value="">-- Select Category --</option>
                {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label>Subcategory (optional)</label>
              <input type="text" value={subcategory} onChange={e => setSubcategory(e.target.value)} placeholder="e.g. electricity bill, passport photo" />
            </div>

            <div className="form-group">
              <label>Tags (comma-separated, optional)</label>
              <input type="text" value={tags} onChange={e => setTags(e.target.value)} placeholder="e.g. 2026, latest, official" />
            </div>

            <div className="form-group">
              <label>Select File *</label>
              <input type="file" onChange={handleFileChange} accept=".pdf,.jpg,.jpeg,.png,.doc,.docx" />
              {file && <div className="file-info" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><FileText size={16} /> {file.name} ({(file.size / 1024).toFixed(1)} KB)</div>}
            </div>

            <div className="form-actions">
              <button className="btn btn-outline" onClick={() => navigate('/documents')}>Cancel</button>
              <button className="btn btn-primary" onClick={handleUpload} disabled={uploading || !file || !displayName.trim() || !category}>
                {uploading ? 'Processing OCR & Uploading...' : 'Upload to Vault'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {showConfirmModal && (
        <div className="modal-overlay" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="modal-content" style={{ maxWidth: 500, width: '90%', padding: '2rem', borderRadius: '12px', background: 'var(--glass-bg)', backdropFilter: 'blur(20px)', border: '1px solid var(--glass-border)' }}>
            <div className="modal-header" style={{ borderBottom: '1px solid var(--glass-border)', paddingBottom: '1rem', marginBottom: '1.5rem' }}>
              <h3 style={{ margin: 0, color: 'var(--sage-300)' }}>📋 OCR Extracted Data</h3>
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
              The AI extracted the following fields from your document. Please verify them before saving to your profile:
            </p>
            <div className="modal-body" style={{ maxHeight: '300px', overflowY: 'auto', marginBottom: '1.5rem' }}>
              {Object.entries(detectedFields).map(([key, val]) => (
                <div className="form-group" key={key} style={{ marginBottom: '1rem' }}>
                  <label style={{ fontSize: '0.8rem', textTransform: 'uppercase', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                    {key.replace(/_/g, ' ')}
                  </label>
                  <input
                    type="text"
                    value={val || ''}
                    onChange={(e) => setDetectedFields(prev => ({ ...prev, [key]: e.target.value }))}
                    style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: 'var(--text-primary)' }}
                  />
                </div>
              ))}
            </div>
            <div className="form-actions" style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
              <button className="btn btn-outline" onClick={() => { setShowConfirmModal(false); navigate('/documents'); }}>
                Discard/Skip
              </button>
              <button className="btn btn-primary" onClick={handleConfirmSave}>
                Save to Profile
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default DocumentUpload
