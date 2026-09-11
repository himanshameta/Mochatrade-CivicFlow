import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const CATEGORY_ICONS = {
  identity: '🆔', address_proof: '🏠', education: '🎓', certificate: '📜',
  photo: '📷', resume: '📋', financial: '💰', medical: '🏥', other: '📄',
}

const CATEGORY_LABELS = {
  identity: 'Identity', address_proof: 'Address Proof', education: 'Education',
  certificate: 'Certificate', photo: 'Photo', resume: 'Resume',
  financial: 'Financial', medical: 'Medical', other: 'Other',
}

const DocumentList = ({ user, showToast }) => {
  const navigate = useNavigate()
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeCategory, setActiveCategory] = useState('all')

  useEffect(() => { loadDocuments() }, [])

  const loadDocuments = async () => {
    try {
      const response = await axios.get('/documents/vault/list')
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
      await axios.delete(`/documents/vault/${docId}`)
      showToast('Document deleted', 'success')
      loadDocuments()
    } catch (error) {
      showToast('Failed to delete document', 'error')
    }
  }

  const categories = ['all', ...new Set(documents.map(d => d.category))]
  const filtered = activeCategory === 'all' ? documents : documents.filter(d => d.category === activeCategory)

  if (loading) return <div className="loading-overlay"><div className="spinner"></div></div>

  return (
    <div className="view active">
      <div className="page-container">
        <div className="page-hero">
          <h2>My Documents</h2>
          <p>Your private document vault — stored locally only</p>
        </div>

        <div className="documents-actions">
          <button className="btn btn-primary" onClick={() => navigate('/documents/upload')}>+ Upload New Document</button>
        </div>

        {/* Category tabs */}
        {documents.length > 0 && (
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
            {categories.map(cat => (
              <button key={cat} onClick={() => setActiveCategory(cat)}
                className={`btn btn-sm ${activeCategory === cat ? 'btn-primary' : 'btn-outline'}`}
                style={{ textTransform: 'capitalize', fontSize: '0.85rem' }}>
                {cat === 'all' ? `📁 All (${documents.length})` : `${CATEGORY_ICONS[cat] || '📄'} ${CATEGORY_LABELS[cat] || cat} (${documents.filter(d => d.category === cat).length})`}
              </button>
            ))}
          </div>
        )}

        {filtered.length === 0 ? (
          <div className="glass-card empty-state">
            <div className="empty-icon">📄</div>
            <h3>{documents.length === 0 ? 'No Documents Yet' : 'No documents in this category'}</h3>
            <p>Upload your first document to get started with automated form filling</p>
            <button className="btn btn-primary" onClick={() => navigate('/documents/upload')}>Upload Document</button>
          </div>
        ) : (
          <div className="documents-grid">
            {filtered.map(doc => (
              <div key={doc.document_id} className="document-card glass-card">
                <div className="document-icon">{CATEGORY_ICONS[doc.category] || '📄'}</div>
                <div className="document-info">
                  <h4>{doc.display_name}</h4>
                  <p className="document-filename">{doc.original_filename}</p>
                  <p style={{ fontSize: '0.75rem', margin: '0.25rem 0' }}>
                    <span style={{ padding: '0.15rem 0.4rem', borderRadius: '4px', background: 'rgba(99,102,241,0.1)', color: '#6366f1', fontSize: '0.7rem', textTransform: 'capitalize' }}>
                      {(doc.category || 'other').replace(/_/g, ' ')}
                    </span>
                    {doc.subcategory && <span style={{ marginLeft: '0.5rem', color: '#6b7280' }}>{doc.subcategory}</span>}
                  </p>
                  <p className="document-date">Uploaded: {new Date(doc.created_at).toLocaleDateString()}</p>
                  {doc.size_bytes > 0 && <p style={{ fontSize: '0.7rem', color: '#9ca3af' }}>{(doc.size_bytes / 1024).toFixed(1)} KB</p>}
                </div>
                <div className="document-actions">
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(doc.document_id)}>Delete</button>
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
