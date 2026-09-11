import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { FolderOpen, X, Folder, FileText, IdCard, Home, GraduationCap, FileBadge, Camera, ClipboardList, CircleDollarSign, Hospital } from 'lucide-react'

const CATEGORY_ICONS = {
  identity: <IdCard size={14} />, address_proof: <Home size={14} />, education: <GraduationCap size={14} />, certificate: <FileBadge size={14} />,
  photo: <Camera size={14} />, resume: <ClipboardList size={14} />, financial: <CircleDollarSign size={14} />, medical: <Hospital size={14} />, other: <FileText size={14} />,
}

const DocumentPickerModal = ({ sessionId, fieldName, fieldLabel, accept, suggestedDocs, onClose, onSelected, showToast }) => {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeCategory, setActiveCategory] = useState('all')

  useEffect(() => { loadDocuments() }, [])

  const loadDocuments = async () => {
    try {
      const res = await axios.get('/documents/vault/list')
      setDocuments(res.data.data.documents || [])
    } catch {
      showToast('Failed to load documents', 'error')
    } finally {
      setLoading(false)
    }
  }

  // Filter by accept types (basic extension matching)
  const isCompatible = (doc) => {
    if (!accept) return true
    const allowed = accept.split(',').map(t => t.trim().toLowerCase())
    const ext = (doc.extension || '').toLowerCase()
    const mime = (doc.mime_type || '').toLowerCase()
    return allowed.some(a => {
      if (a.startsWith('.')) return ext === a
      if (a.endsWith('/*')) return mime.startsWith(a.replace('/*', '/'))
      return mime === a
    })
  }

  const compatible = documents.filter(isCompatible)

  // Merge suggested docs at top
  const suggestedIds = new Set((suggestedDocs || []).map(s => s.document_id))
  const suggested = compatible.filter(d => suggestedIds.has(d.document_id))
  const rest = compatible.filter(d => !suggestedIds.has(d.document_id))

  const categories = ['all', ...new Set(compatible.map(d => d.category))]
  const filtered = activeCategory === 'all' ? [...suggested, ...rest] :
    [...suggested, ...rest].filter(d => d.category === activeCategory)

  const handleSelect = async (doc) => {
    try {
      await axios.post(`/documents/session/${sessionId}/attach-document`, {
        field_name: fieldName,
        document_id: doc.document_id,
      })
      showToast(`${doc.display_name} attached`, 'success')
      onSelected(fieldName, doc.document_id, doc.display_name)
      onClose()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to attach', 'error')
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 600, maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div className="modal-header">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><FolderOpen size={20} /> Choose from My Documents</h3>
          <button className="modal-close" onClick={onClose}><X size={16} /></button>
        </div>
        <p style={{ color: '#6b7280', fontSize: '0.9rem', margin: '0 0 0.75rem 0' }}>
          For: <strong>{fieldLabel}</strong>
          {accept && <span style={{ color: '#9ca3af' }}> ({accept})</span>}
        </p>

        {/* Category tabs */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          {categories.map(cat => (
            <button key={cat} onClick={() => setActiveCategory(cat)}
              className={`btn btn-sm ${activeCategory === cat ? 'btn-primary' : 'btn-outline'}`}
              style={{ textTransform: 'capitalize', fontSize: '0.8rem', padding: '0.25rem 0.75rem' }}>
              {cat === 'all' ? <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}><Folder size={14} /> All</span> : <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', textTransform: 'capitalize' }}>{CATEGORY_ICONS[cat] || <FileText size={14} />} {cat.replace(/_/g, ' ')}</span>}
            </button>
          ))}
        </div>

        {/* Document list */}
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#6b7280' }}>Loading...</div>
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#6b7280' }}>
              <p>No compatible documents found.</p>
              <p style={{ fontSize: '0.85rem' }}>Upload a new one instead.</p>
            </div>
          ) : (
            filtered.map(doc => {
              const isSuggested = suggestedIds.has(doc.document_id)
              return (
                <div key={doc.document_id}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '0.75rem 1rem', marginBottom: '0.5rem', borderRadius: '8px',
                    border: isSuggested ? '1px solid #6ee7b7' : '1px solid rgba(255,255,255,0.1)',
                    background: isSuggested ? 'rgba(16,185,129,0.08)' : 'transparent',
                  }}>
                  <div>
                    <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      {CATEGORY_ICONS[doc.category] || <FileText size={14} />} {doc.display_name}
                      {isSuggested && <span style={{ marginLeft: '0.5rem', fontSize: '0.7rem', color: '#10b981', background: '#d1fae5', padding: '0.15rem 0.4rem', borderRadius: '4px' }}>Suggested</span>}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>
                      {doc.original_filename} · {doc.category.replace(/_/g, ' ')} · {new Date(doc.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <button className="btn btn-sm btn-primary" onClick={() => handleSelect(doc)}>Select</button>
                </div>
              )
            })
          )}
        </div>

        <div className="form-actions" style={{ marginTop: '1rem' }}>
          <button className="btn btn-outline" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  )
}

export default DocumentPickerModal
