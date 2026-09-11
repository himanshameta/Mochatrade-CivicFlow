import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import axios from 'axios'
import Header from './components/Header'
import Login from './components/Login'
import Dashboard from './components/Dashboard'
import FormSearch from './components/FormSearch'
import FormReview from './components/FormReview'
import ExecutionView from './components/ExecutionView'
import ProfileSetup from './components/ProfileSetup'
import SessionDetail from './components/SessionDetail'
import DocumentUpload from './components/DocumentUpload'
import DocumentList from './components/DocumentList'
import ChatBot from './components/ChatBot'
import Toast from './components/Toast'
import './App.css'

axios.defaults.baseURL = 'http://localhost:8000'

function App() {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(localStorage.getItem('token'))
  const [toast, setToast] = useState({ show: false, message: '', type: 'info' })

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
      loadUserProfile()
    }
  }, [token])

  const loadUserProfile = async () => {
    try {
      const response = await axios.get('/auth/me')
      setUser(response.data.data)
    } catch (error) {
      console.error('Failed to load user profile:', error)
      handleLogout()
    }
  }

  const handleLogin = (userData, authToken) => {
    setUser(userData)
    setToken(authToken)
    localStorage.setItem('token', authToken)
    axios.defaults.headers.common['Authorization'] = `Bearer ${authToken}`
  }

  const handleLogout = () => {
    setUser(null)
    setToken(null)
    localStorage.removeItem('token')
    delete axios.defaults.headers.common['Authorization']
  }

  const showToast = (message, type = 'info') => {
    setToast({ show: true, message, type })
    setTimeout(() => setToast({ show: false, message: '', type: 'info' }), 3000)
  }

  return (
    <BrowserRouter>
      <div className="app">
        {user && <Header user={user} onLogout={handleLogout} />}
        {toast.show && <Toast message={toast.message} type={toast.type} />}
        
        <Routes>
          <Route path="/" element={user ? <Navigate to="/dashboard" /> : <Login onLogin={handleLogin} showToast={showToast} />} />
          <Route path="/login" element={user ? <Navigate to="/dashboard" /> : <Login onLogin={handleLogin} showToast={showToast} />} />
          <Route path="/dashboard" element={user ? <Dashboard user={user} showToast={showToast} /> : <Navigate to="/login" />} />
          <Route path="/form-search" element={user ? <FormSearch showToast={showToast} /> : <Navigate to="/login" />} />
          <Route path="/form-review/:sessionId" element={user ? <FormReview showToast={showToast} /> : <Navigate to="/login" />} />
          <Route path="/execution/:sessionId" element={user ? <ExecutionView showToast={showToast} /> : <Navigate to="/login" />} />
          <Route path="/profile-setup" element={user ? <ProfileSetup user={user} showToast={showToast} /> : <Navigate to="/login" />} />
          <Route path="/session/:sessionId" element={user ? <SessionDetail showToast={showToast} /> : <Navigate to="/login" />} />
          <Route path="/documents" element={user ? <DocumentList user={user} showToast={showToast} /> : <Navigate to="/login" />} />
          <Route path="/documents/upload" element={user ? <DocumentUpload user={user} showToast={showToast} /> : <Navigate to="/login" />} />
        </Routes>
        
        {user && <ChatBot user={user} showToast={showToast} />}
      </div>
    </BrowserRouter>
  )
}

export default App
