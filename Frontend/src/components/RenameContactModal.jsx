import React, { useState, useEffect } from 'react'

export default function RenameContactModal({
  isOpen,
  onClose,
  targetUser,
  initialName,
  onSave,
}) {
  const [customName, setCustomName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (isOpen) {
      setCustomName(initialName || targetUser?.full_name || '')
      setError(null)
    }
  }, [isOpen, initialName, targetUser])

  if (!isOpen || !targetUser) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!customName.trim()) {
      setError('Custom name cannot be empty.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const targetUserId = targetUser.contact_user_id || targetUser.id
      await onSave(targetUserId, customName.trim())
      onClose()
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Failed to update custom name.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <div className="modal-header">
          <h3>✏️ Set Custom Name</h3>
          <button type="button" className="close-btn" onClick={onClose} disabled={loading}>
            ✕
          </button>
        </div>

        <p className="modal-subtitle">
          This name is <strong>private to you</strong>. It will not change{' '}
          <strong>{targetUser.original_name || targetUser.full_name}</strong>'s public profile or what others see.
        </p>

        {error && (
          <div className="alert alert-error" style={{ marginBottom: '1rem' }}>
            <span>⚠️ {error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
            <label htmlFor="modalCustomName">Private Custom Name</label>
            <input
              id="modalCustomName"
              type="text"
              placeholder="e.g. Best Friend, Work Colleague"
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              disabled={loading}
              autoFocus
              maxLength={100}
              required
            />
          </div>

          <div className="modal-actions">
            <button
              type="button"
              className="button button-outline"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="button button-primary"
              disabled={loading || !customName.trim()}
            >
              {loading ? 'Saving...' : 'Save Custom Name'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

