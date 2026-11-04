import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState(null)

  const from = location.state?.from?.pathname || '/dashboard'

  const handleLoginSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!email.trim() || !password) {
      setErrorMessage('Please enter both email and password.')
      return
    }

    setLoading(true)
    try {
      await login(email.trim().toLowerCase(), password)
      navigate(from, { replace: true })
    } catch (err) {
      const detail = err.response?.data?.detail
      let msg = 'Login failed. Please check your credentials.'
      if (typeof detail === 'string') {
        msg = detail
      } else if (Array.isArray(detail) && detail.length > 0) {
        msg = detail.map((d) => d.msg || d).join(', ')
      } else if (err.code === 'ECONNABORTED' || (err.message && err.message.includes('timeout'))) {
        msg = 'Connection timed out. The server may be waking up, please try again.'
      } else if (err.message === 'Network Error') {
        msg = 'Unable to reach the server. Please check your internet connection and try again.'
      } else if (err.message) {
        msg = err.message
      }
      setErrorMessage(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        {/* Header */}
        <div className="auth-header">
          <div className="logo-icon">🔐</div>
          <h1>Welcome Back</h1>
          <p className="subtitle">Sign in to your account</p>
        </div>

        {/* Error notification */}
        {errorMessage && (
          <div className="alert alert-error">
            <span>⚠️ {errorMessage}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleLoginSubmit} className="auth-form" noValidate>
          <div className="form-group">
            <label htmlFor="loginEmail">Email Address</label>
            <input
              id="loginEmail"
              type="email"
              placeholder="alice@example.com"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                if (errorMessage) setErrorMessage(null)
              }}
              disabled={loading}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="loginPassword">Password</label>
            <div className="password-input-wrapper">
              <input
                id="loginPassword"
                type={showPassword ? 'text' : 'password'}
                placeholder="Enter your password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  if (errorMessage) setErrorMessage(null)
                }}
                disabled={loading}
                required
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                title={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? '👁️‍🗨️' : '👁️'}
              </button>
            </div>
          </div>

          <button type="submit" className="button button-primary" disabled={loading}>
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>

          <div className="auth-footer">
            <span>Don't have an account? </span>
            <button
              type="button"
              className="link-button"
              onClick={() => navigate('/signup')}
            >
              Sign Up
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
