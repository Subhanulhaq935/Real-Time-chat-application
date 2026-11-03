import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient from '../api/client'

export default function Status() {
  const navigate = useNavigate()
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const checkBackendHealth = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.get('/health')
      setHealth(response.data)
    } catch (err) {
      console.error('Health check failed:', err)
      setError(err.message || 'Failed to reach FastAPI backend')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    checkBackendHealth()
  }, [])

  return (
    <div className="container">
      <header className="header">
        <h1>💬 Real-Time Chatting Application</h1>
        <p className="phase-tag">Phase 3: Signup &amp; Email OTP Verification</p>
      </header>

      <main className="card">
        <h2>System Status</h2>

        <div className="status-grid">
          <div className="status-item">
            <span className="label">Frontend (React + Vite + PWA):</span>
            <span className="badge badge-success">Running</span>
          </div>

          <div className="status-item">
            <span className="label">FastAPI Backend:</span>
            {loading ? (
              <span className="badge badge-pending">Checking...</span>
            ) : error ? (
              <span className="badge badge-error">Offline</span>
            ) : (
              <span className="badge badge-success">{health?.status || 'Online'}</span>
            )}
          </div>

          <div className="status-item">
            <span className="label">PostgreSQL Database:</span>
            {loading ? (
              <span className="badge badge-pending">Checking...</span>
            ) : error ? (
              <span className="badge badge-error">Unreachable</span>
            ) : (
              <span className="badge badge-success">{health?.database || 'Connected'}</span>
            )}
          </div>
        </div>

        {error && (
          <div className="alert alert-error">
            <p><strong>Connection Notice:</strong> {error}</p>
            <small>Make sure the FastAPI backend is running on <code>http://127.0.0.1:8000</code>.</small>
          </div>
        )}

        {health && (
          <div className="alert alert-success">
            <p><strong>App:</strong> {health.app}</p>
            <p><strong>Environment:</strong> {health.environment}</p>
            <p><strong>DB Status:</strong> {health.database}</p>
          </div>
        )}

        <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
          <button className="button button-outline" onClick={checkBackendHealth} disabled={loading}>
            {loading ? 'Testing...' : 'Re-check Connection'}
          </button>
          <button className="button button-primary" onClick={() => navigate('/signup')}>
            Go to Signup
          </button>
        </div>
      </main>

      <footer className="footer">
        <p>Phase 3 Activated: Signup, Gmail SMTP OTP &amp; Verification</p>
      </footer>
    </div>
  )
}

