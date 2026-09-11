import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

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
      await axios.post('/documents/vault/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      showToast('Document uploaded to vault!', 'success')
      navigate('/documents')
    } catch (error) {
      showToast(error.response?.data?.detail || 'Failed to upload document', 'error')
    } finally {
      setUploading(false)
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
              {file && <div className="file-info">📄 {file.name} ({(file.size / 1024).toFixed(1)} KB)</div>}
            </div>

            <div className="form-actions">
              <button className="btn btn-outline" onClick={() => navigate('/documents')}>Cancel</button>
              <button className="btn btn-primary" onClick={handleUpload} disabled={uploading || !file || !displayName.trim() || !category}>
                {uploading ? 'Uploading...' : 'Upload to Vault'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DocumentUpload
