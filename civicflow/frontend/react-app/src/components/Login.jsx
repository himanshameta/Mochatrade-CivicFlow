import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { ArrowRight, Bot, FileText, Lock, Globe } from 'lucide-react'

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

        {/* ── Brand panel ── */}
        <div className="auth-brand">
          <div className="brand-logo">
            {/* Logo — orange-accented checkmark icon */}
            <svg width="52" height="52" viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <rect width="32" height="32" rx="8" fill="url(#loginLogoGrad)"/>
              <path d="M8 16L14 22L24 10" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
              <defs>
                <linearGradient id="loginLogoGrad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#F7931A"/>
                  <stop offset="1" stopColor="#EA580C"/>
                </linearGradient>
              </defs>
            </svg>
            <h1>CivicFlow</h1>
          </div>
          <p className="brand-tagline">AI-powered form automation for any website</p>

          <div className="brand-features">
            <div className="brand-feature">
              <div className="feature-icon" aria-hidden="true"><Bot size={18} /></div>
              <span>Sahayak AI guides you step by step</span>
            </div>
            <div className="brand-feature">
              <div className="feature-icon" aria-hidden="true"><FileText size={18} /></div>
              <span>Auto-extract data from your documents</span>
            </div>
            <div className="brand-feature">
              <div className="feature-icon" aria-hidden="true"><Lock size={18} /></div>
              <span>AES-256 encrypted, zero-trust storage</span>
            </div>
            <div className="brand-feature">
              <div className="feature-icon" aria-hidden="true"><Globe size={18} /></div>
              <span>Works with any form on any website</span>
            </div>
          </div>
        </div>

        {/* ── Auth form card ── */}
        <div className="auth-form-card">
          <div className="auth-form-title">
            {activeTab === 'login' ? 'Sign in to CivicFlow' : 'Create your account'}
          </div>
          <div className="auth-form-subtitle">
            {activeTab === 'login'
              ? 'Welcome back. Enter your credentials to continue.'
              : 'Join CivicFlow and start automating your forms.'}
          </div>

          <div className="auth-tabs" role="tablist">
            <button
              role="tab"
              aria-selected={activeTab === 'login'}
              className={`auth-tab ${activeTab === 'login' ? 'active' : ''}`}
              onClick={() => setActiveTab('login')}
            >
              Sign In
            </button>
            <button
              role="tab"
              aria-selected={activeTab === 'register'}
              className={`auth-tab ${activeTab === 'register' ? 'active' : ''}`}
              onClick={() => setActiveTab('register')}
            >
              Create Account
            </button>
          </div>

          {activeTab === 'login' ? (
            <form onSubmit={handleLogin} noValidate>
              <div className="form-group">
                <label htmlFor="loginEmail">Email Address</label>
                <input
                  type="email"
                  id="loginEmail"
                  value={loginData.email}
                  onChange={(e) => setLoginData({ ...loginData, email: e.target.value })}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="loginPassword">Password</label>
                <input
                  type="password"
                  id="loginPassword"
                  value={loginData.password}
                  onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                />
              </div>
              <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
                {loading ? <><span className="btn-loader"></span> Signing in...</> : <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>Sign In <ArrowRight size={16} /></span>}
              </button>
            </form>
          ) : (
            <form onSubmit={handleRegister} noValidate>
              <div className="form-group">
                <label htmlFor="regName">Full Name</label>
                <input
                  type="text"
                  id="regName"
                  value={registerData.name}
                  onChange={(e) => setRegisterData({ ...registerData, name: e.target.value })}
                  placeholder="Your full name"
                  autoComplete="name"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="regEmail">Email Address</label>
                <input
                  type="email"
                  id="regEmail"
                  value={registerData.email}
                  onChange={(e) => setRegisterData({ ...registerData, email: e.target.value })}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="regPhone">Phone Number</label>
                <input
                  type="tel"
                  id="regPhone"
                  value={registerData.phone}
                  onChange={(e) => setRegisterData({ ...registerData, phone: e.target.value })}
                  placeholder="10-digit number"
                  autoComplete="tel"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="regPassword">Password</label>
                <input
                  type="password"
                  id="regPassword"
                  value={registerData.password}
                  onChange={(e) => setRegisterData({ ...registerData, password: e.target.value })}
                  placeholder="Min 8 characters"
                  autoComplete="new-password"
                  required
                />
              </div>
              <div className="form-group">
                <label>Account Type</label>
                <div className="role-toggle" role="group" aria-label="Account type">
                  <button
                    type="button"
                    className={`role-btn ${registerData.role === 'primary' ? 'active' : ''}`}
                    onClick={() => setRegisterData({ ...registerData, role: 'primary' })}
                    aria-pressed={registerData.role === 'primary'}
                  >
                    Primary Account
                  </button>
                  <button
                    type="button"
                    className={`role-btn ${registerData.role === 'relative' ? 'active' : ''}`}
                    onClick={() => setRegisterData({ ...registerData, role: 'relative' })}
                    aria-pressed={registerData.role === 'relative'}
                  >
                    Relative Account
                  </button>
                </div>
              </div>
              <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
                {loading ? <><span className="btn-loader"></span> Creating...</> : <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>Create Account <ArrowRight size={16} /></span>}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

export default Login
