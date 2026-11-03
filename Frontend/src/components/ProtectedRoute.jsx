import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="auth-container">
        <div className="auth-card" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
          <div className="logo-icon">⏳</div>
          <h2>Checking Authentication...</h2>
          <p className="subtitle">Verifying your secure session</p>
        </div>
      </div>
    )
  }

  if (!user) {
    // Redirect unauthenticated user to /login and preserve attempted URL
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}

