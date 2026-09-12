import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { ArrowRight, Lock } from 'lucide-react'

const ProfileSetup = ({ user, showToast }) => {
  const [profile, setProfile] = useState({
    first_name: '',
    last_name: '',
    dob: '',
    gender: '',
    phone: '',
    address: '',
    city: '',
    state: '',
    pincode: '',
    aadhaar_number: '',
    pan_number: '',
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    loadProfile()
  }, [])

  const loadProfile = async () => {
    try {
      const response = await axios.get('/auth/profile')
      if (response.data && response.data.data && response.data.data.profile) {
        const fetched = response.data.data.profile
        setProfile(prev => ({ ...prev, ...fetched }))
      }
    } catch (error) {
      console.error('Failed to load profile:', error)
      showToast('Failed to load profile', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (field, value) => {
    setProfile(prev => ({ ...prev, [field]: value }))
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)

    const payload = {
      basic_info: {
        first_name: profile.first_name || '',
        last_name: profile.last_name || '',
        dob: profile.dob || '',
        gender: profile.gender || '',
      },
      contact: {
        email: user?.email || profile.email || '',
        phone: profile.phone || '',
        address: profile.address || '',
        city: profile.city || '',
        state: profile.state || '',
        pincode: profile.pincode || '',
      },
      identity: {
        aadhaar_number: profile.aadhaar_number || profile.aadhaar || '',
        pan_number: profile.pan_number || profile.pan || '',
      }
    }

    try {
      const res = await axios.post('/auth/profile', payload)
      if (res.data && res.data.success) {
        showToast('Profile updated securely', 'success')
        navigate('/dashboard')
      } else {
        showToast(res.data?.message || 'Failed to save profile', 'error')
      }
    } catch (error) {
      console.error('Save profile error:', error)
      const errDetail = error.response?.data?.detail
      const msg = typeof errDetail === 'string' ? errDetail : errDetail?.message || error.message || 'Failed to save profile'
      showToast(msg, 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleSkip = () => {
    navigate('/dashboard')
  }

  if (loading) return <div className="loading-overlay"><div className="spinner"></div></div>

  return (
    <div className="view active">
      <div className="page-container" style={{ maxWidth: '800px' }}>
        
        <div className="page-hero">
          <h2>Complete Your Profile</h2>
          <p>This information will be used to automatically fill government forms. All data is encrypted locally.</p>
        </div>

        <div className="glass-card">
          <form onSubmit={handleSave} className="profile-form">
            
            {/* ── Personal Info ── */}
            <div className="profile-section">
              <div className="profile-section-header">
                <h3>Personal Information</h3>
              </div>
              <div className="form-grid">
                <div className="form-group">
                  <label htmlFor="firstName">First Name</label>
                  <input
                    type="text"
                    id="firstName"
                    value={profile.first_name || ''}
                    onChange={(e) => handleChange('first_name', e.target.value)}
                    placeholder="John"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="lastName">Last Name</label>
                  <input
                    type="text"
                    id="lastName"
                    value={profile.last_name || ''}
                    onChange={(e) => handleChange('last_name', e.target.value)}
                    placeholder="Doe"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="dob">Date of Birth</label>
                  <input
                    type="date"
                    id="dob"
                    value={profile.dob || ''}
                    onChange={(e) => handleChange('dob', e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="gender">Gender</label>
                  <select
                    id="gender"
                    value={profile.gender || ''}
                    onChange={(e) => handleChange('gender', e.target.value)}
                  >
                    <option value="">Select...</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>
            </div>

            {/* ── Contact Info ── */}
            <div className="profile-section">
              <div className="profile-section-header">
                <h3>Contact Details</h3>
              </div>
              <div className="form-grid">
                <div className="form-group">
                  <label htmlFor="email">Email</label>
                  <input type="email" id="email" value={user?.email || ''} disabled />
                </div>
                <div className="form-group">
                  <label htmlFor="phone">Phone Number</label>
                  <input
                    type="tel"
                    id="phone"
                    value={profile.phone || ''}
                    onChange={(e) => handleChange('phone', e.target.value)}
                    placeholder="10-digit mobile"
                  />
                </div>
                <div className="form-group full-width">
                  <label htmlFor="address">Full Residential Address</label>
                  <textarea
                    id="address"
                    value={profile.address || ''}
                    onChange={(e) => handleChange('address', e.target.value)}
                    placeholder="Flat/House No., Street, Area..."
                    rows={3}
                  ></textarea>
                </div>
                <div className="form-group">
                  <label htmlFor="city">City</label>
                  <input
                    type="text"
                    id="city"
                    value={profile.city || ''}
                    onChange={(e) => handleChange('city', e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="state">State</label>
                  <input
                    type="text"
                    id="state"
                    value={profile.state || ''}
                    onChange={(e) => handleChange('state', e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="pincode">PIN Code</label>
                  <input
                    type="text"
                    id="pincode"
                    value={profile.pincode || ''}
                    onChange={(e) => handleChange('pincode', e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* ── Identity Docs ── */}
            <div className="profile-section">
              <div className="profile-section-header">
                <h3>Identity Document Numbers</h3>
              </div>
              <p className="step-desc" style={{ marginTop: '-1rem', paddingLeft: '0.85rem' }}>
                You can enter these manually, or extract them automatically by uploading your documents to the Vault later.
              </p>
              <div className="form-grid">
                <div className="form-group">
                  <label htmlFor="aadhaar">Aadhaar Number <span className="field-sensitive-tag"><Lock size={12} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '2px' }} /> Encrypted</span></label>
                  <input
                    type="text"
                    id="aadhaar"
                    value={profile.aadhaar_last4 ? `XXXX XXXX ${profile.aadhaar_last4}` : (profile.aadhaar_number || profile.aadhaar || '')}
                    onChange={(e) => handleChange('aadhaar_number', e.target.value)}
                    placeholder="XXXX XXXX XXXX (12 digits)"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="pan">PAN Number <span className="field-sensitive-tag"><Lock size={12} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '2px' }} /> Encrypted</span></label>
                  <input
                    type="password"
                    id="pan"
                    value={profile.pan_number || profile.pan || ''}
                    onChange={(e) => handleChange('pan_number', e.target.value)}
                    placeholder="ABCDE1234F"
                  />
                </div>
              </div>
            </div>

            <div className="form-actions" style={{ marginTop: '2rem' }}>
              <button type="button" className="btn btn-outline" onClick={handleSkip} disabled={saving}>
                Skip for now
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving...' : <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>Save Profile <ArrowRight size={16} /></span>}
              </button>
            </div>
          </form>
        </div>

      </div>
    </div>
  )
}

export default ProfileSetup
