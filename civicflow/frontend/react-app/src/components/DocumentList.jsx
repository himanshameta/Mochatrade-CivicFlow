import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const DocumentList = ({ user, showToast }) => {
  const navigate = useNavigate()
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadDocuments()
  }, [])

  const loadDocuments = async () => {
    try {
      const response = await axios.get('/documents/list')
      setDocuments(response.data.data.documents || [])
    } catch (error) {
      showToast('Failed to load documents', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (docId) => {
    if (!confirm('Are you sure you want to delete this document?')) return

    try {
      await axios.delete(`/documents/${docId}`)
      showToast('Document deleted successfully', 'success')
      loadDocuments()
    } catch (error) {
      showToast('Failed to delete document', 'error')
    }
  }

  const handleViewFields = async (docId) => {
    try {
      const response = await axios.get(`/documents/${docId}/fields`)
      const fields = response.data.data.fields
      
      let fieldsText = 'Extracted Fields:\n\n'
      Object.entries(fields).forEach(([key, value]) => {
        fieldsText += `${key}: ${value}\n`
      })
      
      alert(fieldsText)
    } catch (error) {
      showToast('Failed to load document fields', 'error')
    }
  }

  if (loading) return <div className="loading-overlay"><div className="spinner"></div></div>

  return (
    <div className="view active">
      <div className="page-container">
        <div className="page-hero">
          <h2>My Documents</h2>
          <p>Manage your uploaded documents</p>
        </div>

        <div className="documents-actions">
          <button className="btn btn-primary" onClick={() => navigate('/documents/upload')}>
            + Upload New Document
          </button>
        </div>

        {documents.length === 0 ? (
          <div className="glass-card empty-state">
            <div className="empty-icon">📄</div>
            <h3>No Documents Yet</h3>
            <p>Upload your first document to get started with automated form filling</p>
            <button className="btn btn-primary" onClick={() => navigate('/documents/upload')}>
              Upload Document
            </button>
          </div>
        ) : (
          <div className="documents-grid">
            {documents.map(doc => (
              <div key={doc.doc_id} className="document-card glass-card">
                <div className="document-icon">
                  {doc.doc_type === 'aadhaar' && '🆔'}
                  {doc.doc_type === 'pan' && '💳'}
                  {doc.doc_type === 'passport' && '🛂'}
                  {doc.doc_type === 'driving_license' && '🚗'}
                  {doc.doc_type === 'voter_id' && '🗳️'}
                  {!['aadhaar', 'pan', 'passport', 'driving_license', 'voter_id'].includes(doc.doc_type) && '📄'}
                </div>
                <div className="document-info">
                  <h4>{doc.doc_type.replace(/_/g, ' ').toUpperCase()}</h4>
                  <p className="document-filename">{doc.original_filename}</p>
                  <p className="document-date">
                    Uploaded: {new Date(doc.uploaded_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="document-actions">
                  <button
                    className="btn btn-sm btn-outline"
                    onClick={() => handleViewFields(doc.doc_id)}
                  >
                    View Fields
                  </button>
                  <button
                    className="btn btn-sm btn-danger"
                    onClick={() => handleDelete(doc.doc_id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default DocumentList
