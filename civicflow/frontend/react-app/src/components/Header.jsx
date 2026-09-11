import React from 'react'
import { Link, useLocation } from 'react-router-dom'

const Header = ({ user, onLogout }) => {
  const location = useLocation()

  const isActive = (path) => location.pathname === path

  return (
    <header className="app-header">
      <div className="header-inner">
        <Link to="/dashboard" className="header-logo">
          <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="8" fill="url(#logoGrad)"/>
            <path d="M8 16L14 22L24 10" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
            <defs>
              <linearGradient id="logoGrad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                <stop stopColor="#8B5CF6"/>
                <stop offset="1" stopColor="#F472B6"/>
              </linearGradient>
            </defs>
          </svg>
          <span className="logo-text">CivicFlow</span>
        </Link>

        <nav className="header-nav">
          <Link 
            to="/dashboard" 
            className={`nav-link ${isActive('/dashboard') ? 'active' : ''}`}
          >
            Dashboard
          </Link>
          <Link 
            to="/form-search" 
            className={`nav-link ${isActive('/form-search') ? 'active' : ''}`}
          >
            Find Form
          </Link>
        </nav>

        <div className="header-right">
          <div className="user-pill">
            <div className="user-avatar">
              {user?.name?.[0]?.toUpperCase() || 'U'}
            </div>
            <span>{user?.name || 'User'}</span>
          </div>
          <button 
            className="btn-icon-only" 
            onClick={onLogout} 
            title="Logout"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>
            </svg>
          </button>
        </div>
      </div>
    </header>
  )
}

export default Header
