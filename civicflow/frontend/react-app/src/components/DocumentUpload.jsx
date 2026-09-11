import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const DocumentUpload = ({ user, showToast }) => {
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [docType, setDocType] = useState('')
  const [uploading, setUploading] = useState(false)
  const [extractedFields, setExtractedFields] = useState(null)
  const [docId, setDocId] = useState(null)
  const [correctedFields, setCorrectedFields] = useState({})

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      if (selectedFile.size > 10 * 1024 * 1024) {
        showToast('File size must be less than 10MB', 'error')
        return
      }
      setFile(selectedFile)
    }
  }

  const handleUpload = async () => {
    if (!file || !docType) {
      showToast('Please select a file and document type', 'warning')
      return
    }

    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    formData.append('doc_type', docType)
    formData.append('session_id', '')

    try {
      const response = await axios.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      const data = response.data.data

      if (data.fallback_mode) {
        showToast(data.message || 'Document uploaded with limited processing', 'warning')
        navigate('/documents')
        return
      }

      setDocId(data.doc_id)
      setExtractedFields(data.extracted_fields || {})
      setCorrectedFields(data.extracted_fields || {})
      showToast('Document processed successfully!', 'success')
    } catch (error) {
      showToast(error.response?.data?.detail || 'Failed to upload document', 'error')
    } finally {
      setUploading(false)
    }
  }

  const handleFieldChange = (key, value) => {
    setCorrectedFields(prev => ({ ...prev, [key]: value }))
  }

  const handleConfirm = async () => {
    try {
      await axios.post(`/documents/confirm/${docId}`, {
        corrected_fields: correctedFields
      })
      showToast('Document saved to profile!', 'success')
      navigate('/documents')
    } catch (error) {
      showToast(error.response?.data?.detail || 'Failed to save document', 'error')
    }
  }

  return (
    <div className="view active">
      <div className="page-container">
        <div className="page-hero">
          <h2>Upload Document</h2>
          <p>Extract information from your documents automatically</p>
        </div>

        <div className="glass-card">
          {!extractedFields ? (
            <div className="upload-panel">
              <div className="form-group">
                <label>Document Type *</label>
                <select value={docType} onChange={(e) => setDocType(e.target.value)} required>
                  <option value="">-- Select Document Type --</option>
                  <option value="aadhaar">Aadhaar Card</option>
                  <option value="pan">PAN Card</option>
                  <option value="passport">Passport</option>
                  <option value="driving_license">Driving License</option>
                  <option value="voter_id">Voter ID</option>
                  <option value="bank_statement">Bank Statement</option>
                  <option value="income_certificate">Income Certificate</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div className="form-group">
                <label>Select File *</label>
                <input
                  type="file"
                  onChange={handleFileChange}
                  accept=".pdf,.jpg,.jpeg,.png"
                />
                {file && (
                  <div className="file-info">
                    📄 {file.name} ({(file.size / 1024).toFixed(2)} KB)
                  </div>
                )}
              </div>

              <div className="form-actions">
                <button className="btn btn-outline" onClick={() => navigate('/documents')}>
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  onClick={handleUpload}
                  disabled={uploading || !file || !docType}
                >
                  {uploading ? 'Processing...' : 'Upload & Extract'}
                </button>
              </div>
            </div>
          ) : (
            <div className="extracted-fields-panel">
              <h3>✅ Extracted Information</h3>
              <p>Review and correct the extracted data below:</p>

              <div className="form-grid">
                {Object.entries(extractedFields).map(([key, value]) => (
                  <div key={key} className="form-group">
                    <label>{key.replace(/_/g, ' ').toUpperCase()}</label>
                    <input
                      type="text"
                      value={correctedFields[key] || ''}
                      onChange={(e) => handleFieldChange(key, e.target.value)}
                    />
                  </div>
                ))}
              </div>

              <div className="form-actions">
                <button
                  className="btn btn-outline"
                  onClick={() => {
                    setExtractedFields(null)
                    setDocId(null)
                    setFile(null)
                  }}
                >
                  Upload Another
                </button>
                <button className="btn btn-primary" onClick={handleConfirm}>
                  Confirm & Save
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default DocumentUpload
