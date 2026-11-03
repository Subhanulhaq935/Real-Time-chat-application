import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  searchUserByEmail,
  getContactsList,
  saveContact,
  updateContactCustomName,
  resetContactCustomName,
} from '../api/contacts'
import { createOrGetChat } from '../api/chats'
import RenameContactModal from '../components/RenameContactModal'

export default function Dashboard() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  // Contacts state
  const [contacts, setContacts] = useState([])
  const [contactsLoading, setContactsLoading] = useState(true)

  // Search state
  const [searchEmail, setSearchEmail] = useState('')
  const [searchResult, setSearchResult] = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState(null)

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [modalTargetUser, setModalTargetUser] = useState(null)
  const [modalInitialName, setModalInitialName] = useState('')

  // Action status notification
  const [actionNotice, setActionNotice] = useState(null)

  // Fetch contacts list on mount
  const fetchContacts = async () => {
    setContactsLoading(true)
    try {
      const data = await getContactsList()
      setContacts(data)
    } catch (err) {
      console.error('Failed to load contacts:', err)
    } finally {
      setContactsLoading(false)
    }
  }

  useEffect(() => {
    fetchContacts()
  }, [])

  // Handle Search
  const handleSearchSubmit = async (e) => {
    e.preventDefault()
    if (!searchEmail.trim()) return

    setSearchLoading(true)
    setSearchError(null)
    setSearchResult(null)
    setActionNotice(null)

    try {
      const result = await searchUserByEmail(searchEmail.trim())
      setSearchResult(result)
    } catch (err) {
      const detail = err.response?.data?.detail
      setSearchError(typeof detail === 'string' ? detail : 'User search failed.')
    } finally {
      setSearchLoading(false)
    }
  }

  // Open Rename / Add Contact Modal
  const openRenameModal = (targetUser, initialName = '') => {
    const targetUserId = targetUser.contact_user_id || targetUser.id
    setModalTargetUser({
      ...targetUser,
      id: targetUserId,
      contact_user_id: targetUserId,
    })
    setModalInitialName(initialName)
    setModalOpen(true)
  }

  // Save Custom Name (from modal)
  const handleSaveCustomName = async (targetUserId, newName) => {
    await updateContactCustomName(targetUserId, newName)
    setActionNotice(`Custom name updated to "${newName}".`)
    await fetchContacts()

    // If active search result was this user, update search result display
    if (searchResult && searchResult.id === targetUserId) {
      setSearchResult((prev) => ({
        ...prev,
        custom_name: newName,
        display_name: newName,
        is_contact: true,
      }))
    }
  }

  // Reset Custom Name
  const handleResetName = async (contactUserId) => {
    if (!window.confirm('Reset this custom name back to the user’s original name?')) return

    try {
      await resetContactCustomName(contactUserId)
      setActionNotice('Custom name has been reset.')
      await fetchContacts()

      if (searchResult && searchResult.id === contactUserId) {
        setSearchResult((prev) => ({
          ...prev,
          custom_name: null,
          display_name: prev.full_name,
          is_contact: false,
        }))
      }
    } catch (err) {
      const detail = err.response?.data?.detail
      alert(detail || 'Failed to reset custom name.')
    }
  }

  // Start or open 1-to-1 conversation
  const handleStartChat = async (targetUserId) => {
    try {
      const chat = await createOrGetChat(targetUserId)
      navigate(`/chat?id=${chat.id}`)
    } catch (err) {
      const detail = err.response?.data?.detail
      alert(detail || 'Failed to start or retrieve chat.')
    }
  }

  return (
    <div className="container dashboard-container">
      <div className="card dashboard-card">
        {/* User Profile Header */}
        <header className="dashboard-header">
          <div className="avatar-wrapper">
            <div className="avatar-circle">
              {user?.full_name?.charAt(0).toUpperCase() || 'U'}
            </div>
            <span className="online-dot" title="Online" />
          </div>
          <div className="user-info">
            <div className="user-title-row">
              <h2>{user?.full_name}</h2>
              <span className="badge badge-success">✓ Verified</span>
            </div>
            <p className="subtitle">{user?.email}</p>
          </div>
          <div className="header-actions">
            <button
              type="button"
              className="button button-chat-cta"
              onClick={() => navigate('/chat')}
            >
              💬 Open Chats
            </button>
          </div>
        </header>

        {/* Global Action Notice */}
        {actionNotice && (
          <div className="alert alert-success" style={{ marginTop: '1.25rem' }}>
            <span>✅ {actionNotice}</span>
          </div>
        )}

        {/* SECTION 1: SEARCH REGISTERED USERS */}
        <section className="dashboard-section">
          <div className="section-header">
            <div>
              <h3>🔍 Find People</h3>
              <p className="section-desc">
                Search any verified user by their email address to start a chat or save them to your contacts.
              </p>
            </div>
          </div>

          <form onSubmit={handleSearchSubmit} className="search-form">
            <input
              type="email"
              placeholder="Enter email address (e.g. user@example.com)..."
              value={searchEmail}
              onChange={(e) => {
                setSearchEmail(e.target.value)
                setSearchError(null)
              }}
              disabled={searchLoading}
              required
            />
            <button
              type="submit"
              className="button button-primary search-btn"
              disabled={searchLoading || !searchEmail.trim()}
            >
              {searchLoading ? 'Searching...' : 'Search'}
            </button>
          </form>

          {/* Search Error */}
          {searchError && (
            <div className="alert alert-error" style={{ marginTop: '1rem' }}>
              <span>⚠️ {searchError}</span>
            </div>
          )}

          {/* Search Result Card */}
          {searchResult && (
            <div className="search-result-card">
              <div className="result-avatar">
                {searchResult.display_name?.charAt(0).toUpperCase()}
              </div>
              <div className="result-info">
                <div className="contact-name-row">
                  <h4>{searchResult.display_name}</h4>
                  {searchResult.custom_name && searchResult.custom_name !== searchResult.full_name && (
                    <span className="original-name-pill">~ {searchResult.full_name}</span>
                  )}
                </div>
                <p className="result-email">{searchResult.email}</p>
              </div>
              <div className="result-actions">
                <button
                  type="button"
                  className="button button-outline btn-sm"
                  onClick={() =>
                    openRenameModal(searchResult, searchResult.custom_name || searchResult.full_name)
                  }
                >
                  {searchResult.is_contact ? '✏️ Rename' : '➕ Save'}
                </button>
                {searchResult.is_contact && (
                  <button
                    type="button"
                    className="button button-outline btn-sm btn-danger-outline"
                    onClick={() => handleResetName(searchResult.id)}
                  >
                    Reset
                  </button>
                )}
                <button
                  type="button"
                  className="button button-whatsapp btn-sm"
                  onClick={() => handleStartChat(searchResult.id)}
                >
                  💬 Message
                </button>
              </div>
            </div>
          )}
        </section>

        {/* SECTION 2: MY CONTACTS LIST */}
        <section className="dashboard-section">
          <div className="section-header">
            <div>
              <h3>👥 Saved Contacts ({contacts.length})</h3>
              <p className="section-desc">
                Your private contact list. Custom names are only visible to you.
              </p>
            </div>
            <button
              type="button"
              className="button button-outline btn-sm refresh-btn"
              onClick={fetchContacts}
              disabled={contactsLoading}
            >
              ↻ Refresh
            </button>
          </div>

          {contactsLoading ? (
            <div className="empty-state">
              <p>Loading your contacts...</p>
            </div>
          ) : contacts.length === 0 ? (
            <div className="empty-state">
              <p>📭 No saved contacts yet</p>
              <small>Search for a user above by email to message them or save them as a contact.</small>
            </div>
          ) : (
            <div className="contacts-list">
              {contacts.map((c) => (
                <div key={c.id} className="contact-card">
                  <div className="contact-avatar">
                    {c.display_name?.charAt(0).toUpperCase()}
                  </div>
                  <div className="contact-details">
                    <div className="contact-name-row">
                      <h4>{c.display_name}</h4>
                      {c.display_name !== c.original_name && (
                        <span className="original-name-pill">~ {c.original_name}</span>
                      )}
                    </div>
                    <p className="contact-email">{c.email}</p>
                  </div>
                  <div className="contact-actions">
                    <button
                      type="button"
                      className="button button-outline btn-sm"
                      onClick={() => openRenameModal(c, c.custom_name)}
                      title="Set private custom name"
                    >
                      ✏️ Rename
                    </button>
                    <button
                      type="button"
                      className="button button-outline btn-sm btn-danger-outline"
                      onClick={() => handleResetName(c.contact_user_id)}
                      title="Remove custom name"
                    >
                      Reset
                    </button>
                    <button
                      type="button"
                      className="button button-whatsapp btn-sm"
                      onClick={() => handleStartChat(c.contact_user_id)}
                    >
                      💬 Message
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Rename / Add Contact Modal */}
      <RenameContactModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        targetUser={modalTargetUser}
        initialName={modalInitialName}
        onSave={handleSaveCustomName}
      />
    </div>
  )
}
