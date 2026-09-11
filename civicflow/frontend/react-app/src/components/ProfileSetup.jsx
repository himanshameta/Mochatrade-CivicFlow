import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const ProfileSetup = ({ user, showToast }) => {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [profileData, setProfileData] = useState({
    basic_info: {
      full_name: '',
      date_of_birth: '',
      gender: '',
      father_name: '',
      mother_name: ''
    },
    contact: {
      email: '',
      phone: '',
      address_line1: '',
      address_line2: '',
      city: '',
      state: '',
      pincode: '',
      country: 'India'
    },
    identity: {
      aadhaar_number: '',
      pan_number: '',
      voter_id: '',
      passport_number: ''
    },
    education: {
      highest_qualification: '',
      institution_name: '',
      year_of_passing: ''
    }
  })

  useEffect(() => {
    loadProfile()
  }, [])

  const loadProfile = async () => {
    try {
      const response = await axios.get('/auth/me')
      if (response.data.data) {
        setProfileData(prev => ({
          ...prev,
          contact: {
            ...prev.contact,
            email: response.data.data.email || '',
            phone: response.data.data.phone || ''
          }
        }))
      }
    } catch (error) {
      console.error('Failed to load profile:', error)
    }
  }

  const handleInputChange = (section, field, value) => {
    setProfileData(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value
      }
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)

    try {
      const response = await axios.post('/auth/profile', profileData)
      const data = response.data

      if (data.success) {
        const fieldCount = data.data?.fields_written?.length || 0
        const warningCount = data.data?.warnings?.length || 0
        let msg = `Profile saved (${fieldCount} fields)`
        if (warningCount > 0) {
          msg += ` — ${warningCount} warning(s)`
        }
        showToast(msg, 'success')
        navigate('/dashboard')
      } else {
        // success: false from backend (validation errors)
        const errors = data.errors || [data.message || 'Unknown error']
        showToast(`Profile update failed: ${errors.join(', ')}`, 'error')
      }
    } catch (error) {
      // 422 or other HTTP errors
      const detail = error.response?.data?.detail
      if (detail && typeof detail === 'object') {
        const errors = detail.errors || [detail.message || 'Update failed']
        showToast(`Profile error: ${errors.join(', ')}`, 'error')
      } else {
        showToast(error.response?.data?.detail || 'Failed to update profile', 'error')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="view active">
      <div className="page-container">
        <div className="page-hero">
          <h2>Complete Your Profile</h2>
          <p>Save your information for faster form filling</p>
        </div>

        <form onSubmit={handleSubmit} className="glass-card profile-form">
          <div className="profile-section">
            <h3>📋 Basic Information</h3>
            <div className="form-grid">
              <div className="form-group">
                <label>Full Name *</label>
                <input
                  type="text"
                  value={profileData.basic_info.full_name}
                  onChange={(e) => handleInputChange('basic_info', 'full_name', e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Date of Birth</label>
                <input
                  type="date"
                  value={profileData.basic_info.date_of_birth}
                  onChange={(e) => handleInputChange('basic_info', 'date_of_birth', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Gender</label>
                <select
                  value={profileData.basic_info.gender}
                  onChange={(e) => handleInputChange('basic_info', 'gender', e.target.value)}
                >
                  <option value="">-- Select --</option>
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div className="form-group">
                <label>Father's Name</label>
                <input
                  type="text"
                  value={profileData.basic_info.father_name}
                  onChange={(e) => handleInputChange('basic_info', 'father_name', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Mother's Name</label>
                <input
                  type="text"
                  value={profileData.basic_info.mother_name}
                  onChange={(e) => handleInputChange('basic_info', 'mother_name', e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="profile-section">
            <h3>📞 Contact Information</h3>
            <div className="form-grid">
              <div className="form-group">
                <label>Email *</label>
                <input
                  type="email"
                  value={profileData.contact.email}
                  onChange={(e) => handleInputChange('contact', 'email', e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Phone *</label>
                <input
                  type="tel"
                  value={profileData.contact.phone}
                  onChange={(e) => handleInputChange('contact', 'phone', e.target.value)}
                  required
                />
              </div>
              <div className="form-group full-width">
                <label>Address Line 1</label>
                <input
                  type="text"
                  value={profileData.contact.address_line1}
                  onChange={(e) => handleInputChange('contact', 'address_line1', e.target.value)}
                />
              </div>
              <div className="form-group full-width">
                <label>Address Line 2</label>
                <input
                  type="text"
                  value={profileData.contact.address_line2}
                  onChange={(e) => handleInputChange('contact', 'address_line2', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>City</label>
                <input
                  type="text"
                  value={profileData.contact.city}
                  onChange={(e) => handleInputChange('contact', 'city', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>State</label>
                <input
                  type="text"
                  value={profileData.contact.state}
                  onChange={(e) => handleInputChange('contact', 'state', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Pincode</label>
                <input
                  type="text"
                  value={profileData.contact.pincode}
                  onChange={(e) => handleInputChange('contact', 'pincode', e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="profile-section">
            <h3>🆔 Identity Documents</h3>
            <div className="form-grid">
              <div className="form-group">
                <label>Aadhaar Number</label>
                <input
                  type="text"
                  value={profileData.identity.aadhaar_number}
                  onChange={(e) => handleInputChange('identity', 'aadhaar_number', e.target.value)}
                  maxLength="12"
                />
              </div>
              <div className="form-group">
                <label>PAN Number</label>
                <input
                  type="text"
                  value={profileData.identity.pan_number}
                  onChange={(e) => handleInputChange('identity', 'pan_number', e.target.value)}
                  maxLength="10"
                />
              </div>
              <div className="form-group">
                <label>Voter ID</label>
                <input
                  type="text"
                  value={profileData.identity.voter_id}
                  onChange={(e) => handleInputChange('identity', 'voter_id', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Passport Number</label>
                <input
                  type="text"
                  value={profileData.identity.passport_number}
                  onChange={(e) => handleInputChange('identity', 'passport_number', e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="profile-section">
            <h3>🎓 Education</h3>
            <div className="form-grid">
              <div className="form-group">
                <label>Highest Qualification</label>
                <select
                  value={profileData.education.highest_qualification}
                  onChange={(e) => handleInputChange('education', 'highest_qualification', e.target.value)}
                >
                  <option value="">-- Select --</option>
                  <option value="High School">High School</option>
                  <option value="Diploma">Diploma</option>
                  <option value="Bachelor's">Bachelor's</option>
                  <option value="Master's">Master's</option>
                  <option value="Doctorate">Doctorate</option>
                </select>
              </div>
              <div className="form-group">
                <label>Institution Name</label>
                <input
                  type="text"
                  value={profileData.education.institution_name}
                  onChange={(e) => handleInputChange('education', 'institution_name', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Year of Passing</label>
                <input
                  type="text"
                  value={profileData.education.year_of_passing}
                  onChange={(e) => handleInputChange('education', 'year_of_passing', e.target.value)}
                  maxLength="4"
                />
              </div>
            </div>
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-outline" onClick={() => navigate('/dashboard')}>
              Skip for Now
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Saving...' : 'Save Profile'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default ProfileSetup
