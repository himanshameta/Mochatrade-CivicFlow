import React from 'react'
import { Link, useLocation } from 'react-router-dom'

const Header = ({ user, onLogout }) => {
  const location = useLocation()

  const isActive = (path) => location.pathname === path

  return (
    <header className="app-header">
      <div className="header-inner">
        <Link to="/dashboard" className="header-logo d-flex align-items-center">
          <img src="/logo.png" alt="CivicFlow" className='mt-{-14px}' height={60} />
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
              {(user?.name || user?.email?.split('@')[0] || 'U')[0].toUpperCase()}
            </div>
            <span>
              {user?.name || (user?.email 
                ? user.email.split('@')[0].split(/[._-]/).map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ') 
                : 'User')}
            </span>
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
