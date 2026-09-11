import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

import { FileText, IdCard, Home, GraduationCap, FileBadge, Camera, ClipboardList, CircleDollarSign, Hospital } from 'lucide-react'

const CATEGORY_ICONS = {
  identity: <IdCard size={18} />, address_proof: <Home size={18} />, education: <GraduationCap size={18} />, certificate: <FileBadge size={18} />,
  photo: <Camera size={18} />, resume: <ClipboardList size={18} />, financial: <CircleDollarSign size={18} />, medical: <Hospital size={18} />, other: <FileText size={18} />,
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

        {/* ── Hero ── */}
        <div className="page-hero">
          <h2>My Documents</h2>
          <p>Your private document vault — stored securely, never shared</p>
        </div>

        {/* ── Actions row ── */}
        <div className="documents-actions">
          <button
            className="btn btn-primary"
            onClick={() => navigate('/documents/upload')}
            aria-label="Upload new document"
          >
            + Upload Document
          </button>
        </div>

        {/* ── Category filter tabs ── */}
        {documents.length > 0 && (
          <div className="doc-filter-tabs" role="tablist" aria-label="Filter by category">
            {categories.map(cat => (
              <button
                key={cat}
                role="tab"
                aria-selected={activeCategory === cat}
                className={`doc-filter-tab${activeCategory === cat ? ' active' : ''}`}
                onClick={() => setActiveCategory(cat)}
              >
                {cat === 'all'
                  ? `All (${documents.length})`
                  : <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>{CATEGORY_ICONS[cat] || <FileText size={16} />} {CATEGORY_LABELS[cat] || cat} ({documents.filter(d => d.category === cat).length})</span>
                }
              </button>
            ))}
          </div>
        )}

        {/* ── Grid or empty state ── */}
        {filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"><FileText size={48} /></div>
            <h3>{documents.length === 0 ? 'No Documents Yet' : 'No documents in this category'}</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
              Upload your first document to get started with automated form filling
            </p>
            <button className="btn btn-primary" onClick={() => navigate('/documents/upload')}>
              Upload Document
            </button>
          </div>
        ) : (
          <div className="documents-grid">
            {filtered.map(doc => (
              <article key={doc.document_id} className="document-card">
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
                  <div className="document-icon">
                    {CATEGORY_ICONS[doc.category] || <FileText size={24} />}
                  </div>
                  <div className="document-info">
                    <h4>{doc.display_name}</h4>
                    <p className="document-filename">{doc.original_filename}</p>
                    <div className="document-meta">
                      <span className="doc-category-badge">
                        {(doc.category || 'other').replace(/_/g, ' ')}
                      </span>
                      {doc.subcategory && (
                        <span className="text-muted" style={{ fontSize: '0.72rem' }}>{doc.subcategory}</span>
                      )}
                      {doc.size_bytes > 0 && (
                        <span className="doc-size">{(doc.size_bytes / 1024).toFixed(1)} KB</span>
                      )}
                    </div>
                    <p className="document-date">
                      Uploaded: {new Date(doc.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="document-actions">
                  <button
                    className="btn btn-sm btn-danger"
                    onClick={() => handleDelete(doc.document_id)}
                    aria-label={`Delete ${doc.display_name}`}
                  >
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default DocumentList
