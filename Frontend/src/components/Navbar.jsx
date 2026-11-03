import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleNavLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <nav className="top-nav">
      <Link to={user ? "/dashboard" : "/"} className="brand">
        <span className="brand-icon">💬</span>
        <span className="brand-text">ChatApp</span>
      </Link>
      <div className="nav-links">
        {user ? (
          <>
            <Link to="/dashboard" className="nav-link">Dashboard</Link>
            <Link to="/chat" className="nav-link">Chats</Link>
            <span className="user-greeting nav-user-greeting">👤 {user.full_name?.split(' ')[0]}</span>
            <button
              type="button"
              className="button-link"
              onClick={handleNavLogout}
              style={{ color: '#f87171' }}
            >
              Sign Out
            </button>
          </>
        ) : (
          <>
            <Link to="/signup" className="nav-link">Sign Up</Link>
            <Link to="/login" className="nav-link">Log In</Link>
          </>
        )}
        <Link to="/status" className="nav-link nav-badge">Status</Link>
      </div>
    </nav>
  )
}

