import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const Login = ({ onLogin, showToast }) => {
  const [activeTab, setActiveTab] = useState('login')
  const [loginData, setLoginData] = useState({ email: '', password: '' })
  const [registerData, setRegisterData] = useState({
    name: '', email: '', phone: '', password: '', role: 'primary'
  })
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)

    try {
      const response = await axios.post('/auth/login', loginData)
      onLogin(response.data.data.user, response.data.data.access_token)
      showToast('Login successful!', 'success')
      navigate('/dashboard')
    } catch (error) {
      showToast(error.response?.data?.detail || 'Login failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    setLoading(true)

    try {
      const response = await axios.post('/auth/register', registerData)
      onLogin(response.data.data.user, response.data.data.access_token)
      showToast('Account created successfully!', 'success')
      navigate('/profile-setup')
    } catch (error) {
      showToast(error.response?.data?.detail || 'Registration failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="view active" id="view-login">
      <div className="auth-layout">
        <div className="auth-brand">
          <div className="brand-logo">
            <svg width="48" height="48" viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="8" fill="url(#logoGrad2)"/>
              <path d="M8 16L14 22L24 10" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
              <defs>
                <linearGradient id="logoGrad2" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#86b89a"/>
                  <stop offset="1" stopColor="#4a8a64"/>
                </linearGradient>
              </defs>
            </svg>
            <h1>CivicFlow</h1>
          </div>
          <p className="brand-tagline">AI-powered form filling for any website</p>
          <div className="brand-features">
            <div className="brand-feature"><span>🤖</span> Sahayak guides you step by step</div>
            <div className="brand-feature"><span>📄</span> Auto-extract from your documents</div>
            <div className="brand-feature"><span>🔒</span> AES-256 encrypted, zero-trust storage</div>
            <div className="brand-feature"><span>🌐</span> Works with any form on any website</div>
          </div>
        </div>

        <div className="auth-form-card glass-card">
          <div className="auth-tabs">
            <button 
              className={`auth-tab ${activeTab === 'login' ? 'active' : ''}`}
              onClick={() => setActiveTab('login')}
            >
              Sign In
            </button>
            <button 
              className={`auth-tab ${activeTab === 'register' ? 'active' : ''}`}
              onClick={() => setActiveTab('register')}
            >
              Create Account
            </button>
          </div>

          {activeTab === 'login' ? (
            <form onSubmit={handleLogin}>
              <div className="form-group">
                <label htmlFor="loginEmail">Email Address</label>
                <input
                  type="email"
                  id="loginEmail"
                  value={loginData.email}
                  onChange={(e) => setLoginData({...loginData, email: e.target.value})}
                  placeholder="you@example.com"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="loginPassword">Password</label>
                <input
                  type="password"
                  id="loginPassword"
                  value={loginData.password}
                  onChange={(e) => setLoginData({...loginData, password: e.target.value})}
                  placeholder="••••••••"
                  required
                />
              </div>
              <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
                {loading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleRegister}>
              <div className="form-group">
                <label htmlFor="regName">Full Name</label>
                <input
                  type="text"
                  id="regName"
                  value={registerData.name}
                  onChange={(e) => setRegisterData({...registerData, name: e.target.value})}
                  placeholder="Your full name"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="regEmail">Email Address</label>
                <input
                  type="email"
                  id="regEmail"
                  value={registerData.email}
                  onChange={(e) => setRegisterData({...registerData, email: e.target.value})}
                  placeholder="you@example.com"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="regPhone">Phone Number</label>
                <input
                  type="tel"
                  id="regPhone"
                  value={registerData.phone}
                  onChange={(e) => setRegisterData({...registerData, phone: e.target.value})}
                  placeholder="10-digit number"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="regPassword">Password</label>
                <input
                  type="password"
                  id="regPassword"
                  value={registerData.password}
                  onChange={(e) => setRegisterData({...registerData, password: e.target.value})}
                  placeholder="Min 8 characters"
                  required
                />
              </div>
              <div className="form-group">
                <label>Account Type</label>
                <div className="role-toggle">
                  <button
                    type="button"
                    className={`role-btn ${registerData.role === 'primary' ? 'active' : ''}`}
                    onClick={() => setRegisterData({...registerData, role: 'primary'})}
                  >
                    Primary Account
                  </button>
                  <button
                    type="button"
                    className={`role-btn ${registerData.role === 'relative' ? 'active' : ''}`}
                    onClick={() => setRegisterData({...registerData, role: 'relative'})}
                  >
                    Relative Account
                  </button>
                </div>
              </div>
              <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
                {loading ? 'Creating...' : 'Create Account'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

export default Login
