import React, { useState, useRef } from 'react'
import axios from 'axios'
import { Upload, FileText, UploadCloud } from 'lucide-react'

const CATEGORIES = [
  { value: 'identity', label: 'Identity' },
  { value: 'address_proof', label: 'Address Proof' },
  { value: 'education', label: 'Education' },
  { value: 'certificate', label: 'Certificate' },
  { value: 'photo', label: 'Photo' },
  { value: 'resume', label: 'Resume' },
  { value: 'financial', label: 'Financial' },
  { value: 'medical', label: 'Medical' },
  { value: 'other', label: 'Other' },
]

const FileUploadModal = ({ sessionId, fieldName, fieldLabel, accept, onClose, onUploaded, showToast }) => {
  const [file, setFile] = useState(null)
  const [displayName, setDisplayName] = useState('')
  const [category, setCategory] = useState('other')
  const [saveForReuse, setSaveForReuse] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const inputRef = useRef(null)

  const handleDrop = (e) => {
    e.preventDefault()
    setDragActive(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) {
      setFile(dropped)
      if (!displayName) setDisplayName(dropped.name.replace(/\.[^.]+$/, ''))
    }
  }

  const handleFileChange = (e) => {
    const f = e.target.files[0]
    if (f) {
      if (f.size > 10 * 1024 * 1024) {
        showToast('File must be under 10 MB', 'error')
        return
      }
      setFile(f)
      if (!displayName) setDisplayName(f.name.replace(/\.[^.]+$/, ''))
    }
  }

  const handleUpload = async () => {
    if (!file || !displayName.trim()) {
      showToast('Please select a file and enter a display name', 'warning')
      return
    }
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    formData.append('field_name', fieldName)
    formData.append('display_name', displayName.trim())
    formData.append('category', category)
    formData.append('save_for_reuse', saveForReuse)

    try {
      const res = await axios.post(`/documents/session/${sessionId}/upload-document`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      showToast('File uploaded successfully!', 'success')
      onUploaded(fieldName, res.data.data.document_id)
      onClose()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Upload failed', 'error')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 520 }}>
        <div className="modal-header">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Upload size={20} /> Upload File</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <p style={{ color: '#6b7280', fontSize: '0.9rem', marginBottom: '1rem' }}>
          For: <strong>{fieldLabel}</strong>
          {accept && <span style={{ color: '#9ca3af' }}> ({accept})</span>}
        </p>

        {/* Drop zone */}
        <div
          className={`drop-zone ${dragActive ? 'drop-zone-active' : ''}`}
          onDragOver={e => { e.preventDefault(); setDragActive(true) }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
        >
          {file ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><FileText size={16} /> <strong>{file.name}</strong> ({(file.size / 1024).toFixed(1)} KB)</div>
          ) : (
            <div>
              <div style={{ marginBottom: '0.5rem' }}><UploadCloud size={48} color="var(--accent)" /></div>
              <div>Drag & drop or click to browse</div>
            </div>
          )}
          <input ref={inputRef} type="file" accept={accept} onChange={handleFileChange} style={{ display: 'none' }} />
        </div>

        {/* Display name */}
        <div className="form-group" style={{ marginTop: '1rem' }}>
          <label>Display Name *</label>
          <input type="text" value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="e.g. My Resume 2026" />
        </div>

        {/* Category */}
        <div className="form-group">
          <label>Category</label>
          <select value={category} onChange={e => setCategory(e.target.value)}>
            {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </div>

        {/* Save for reuse */}
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: '0.75rem 0', cursor: 'pointer', fontSize: '0.9rem' }}>
          <input type="checkbox" checked={saveForReuse} onChange={e => setSaveForReuse(e.target.checked)} />
          Save to My Documents for future reuse
        </label>

        <div className="form-actions" style={{ marginTop: '1rem' }}>
          <button className="btn btn-outline" onClick={onClose} disabled={uploading}>Cancel</button>
          <button className="btn btn-primary" onClick={handleUpload} disabled={uploading || !file || !displayName.trim()}>
            {uploading ? 'Uploading...' : 'Upload & Attach'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default FileUploadModal
