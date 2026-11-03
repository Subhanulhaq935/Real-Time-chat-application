import React, { useState, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getChatsList, getChatMessages, sendMessageRest, markChatAsRead } from '../api/chats'

export default function Chat() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [conversations, setConversations] = useState([])
  const [loadingChats, setLoadingChats] = useState(true)
  const [activeConv, setActiveConv] = useState(null)

  const [messages, setMessages] = useState([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [inputText, setInputText] = useState('')

  // WebSocket state
  const [wsStatus, setWsStatus] = useState('disconnected') // 'connecting' | 'connected' | 'disconnected'
  const wsRef = useRef(null)
  const userWsRef = useRef(null)
  const activeConvRef = useRef(null)
  const messagesEndRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const userReconnectTimeoutRef = useRef(null)

  useEffect(() => {
    activeConvRef.current = activeConv
  }, [activeConv])

  // Mobile navigation state
  const [showMobileList, setShowMobileList] = useState(!searchParams.get('id'))

  const handleMobileBack = () => {
    setShowMobileList(true)
    setActiveConv(null)
    setSearchParams({})
  }

  // 1. Fetch Conversations List
  const loadConversations = async (silent = false) => {
    try {
      const data = await getChatsList()
      setConversations((prev) => {
        const currentActiveId = activeConvRef.current?.id
        return data.map((conv) =>
          conv.id === currentActiveId ? { ...conv, unread_count: 0 } : conv
        )
      })

      if (!silent) {
        const targetId = searchParams.get('id')
        if (targetId) {
          const found = data.find((c) => c.id === targetId)
          if (found) {
            setActiveConv(found)
            setShowMobileList(false)
          }
        }
      }
    } catch (err) {
      console.error('Failed to load conversations:', err)
    } finally {
      if (!silent) setLoadingChats(false)
    }
  }

  useEffect(() => {
    loadConversations(false)

    // Background silent sync every 2.5s so sidebar unread badges & previews stay live
    const pollInterval = setInterval(() => {
      loadConversations(true)
    }, 2500)

    return () => clearInterval(pollInterval)
  }, [])

  // 1b. User-Level Real-Time Stream (updates sidebar even when no chat is selected)
  useEffect(() => {
    if (!user?.id) return
    let isMounted = true

    const connectUserStream = () => {
      if (userWsRef.current) {
        userWsRef.current.close()
      }

      const token = localStorage.getItem('access_token') || ''
      const wsBase = import.meta.env.VITE_WS_BASE_URL || 'ws://127.0.0.1:8000'
      const wsUrl = `${wsBase}/ws/user${token ? `?token=${token}` : ''}`

      const socket = new WebSocket(wsUrl)
      userWsRef.current = socket

      socket.onmessage = (event) => {
        if (!isMounted) return
        try {
          const payload = JSON.parse(event.data)
          if (payload.type === 'new_message' && payload.message) {
            const newMsg = payload.message
            const isFromMe = Boolean(
              user?.id && String(newMsg.sender_id).toLowerCase() === String(user.id).toLowerCase()
            )
            const currentActiveId = activeConvRef.current?.id

            setConversations((prev) => {
              const exists = prev.some((c) => c.id === newMsg.conversation_id)
              if (!exists) {
                loadConversations(true)
                return prev
              }

              const updated = prev.map((c) => {
                if (c.id === newMsg.conversation_id) {
                  // Avoid double-counting if this exact message was already recorded as last_message
                  if (c.last_message?.id === newMsg.id) return c
                  const isActive = currentActiveId === c.id
                  const newUnread = isActive || isFromMe ? 0 : (c.unread_count || 0) + 1
                  return {
                    ...c,
                    last_message: {
                      ...newMsg,
                      is_mine: isFromMe,
                    },
                    unread_count: newUnread,
                    updated_at: newMsg.created_at,
                  }
                }
                return c
              })

              // Sort most recently updated conversation to top
              return [...updated].sort(
                (a, b) => new Date(b.updated_at) - new Date(a.updated_at)
              )
            })
          }
        } catch (err) {
          console.error('Error in user stream:', err)
        }
      }

      socket.onclose = (event) => {
        if (!isMounted) return
        if (event.code !== 1008) {
          userReconnectTimeoutRef.current = setTimeout(() => {
            if (isMounted) connectUserStream()
          }, 3000)
        }
      }
    }

    connectUserStream()

    return () => {
      isMounted = false
      if (userReconnectTimeoutRef.current) clearTimeout(userReconnectTimeoutRef.current)
      if (userWsRef.current) {
        userWsRef.current.close()
        userWsRef.current = null
      }
    }
  }, [user?.id])

  // 2. Fetch Messages History when Active Conversation Changes
  const loadMessages = async (conversationId) => {
    setLoadingMessages(true)
    try {
      const res = await getChatMessages(conversationId)
      const list = res.messages || []
      setMessages(list)

      // If there are unread incoming messages, mark conversation as read
      const hasUnread = list.some((m) => !m.is_mine && !m.is_read)
      if (hasUnread) {
        markChatAsRead(conversationId).catch(() => {})
      }
    } catch (err) {
      console.error('Failed to load messages:', err)
    } finally {
      setLoadingMessages(false)
    }
  }

  useEffect(() => {
    if (activeConv) {
      loadMessages(activeConv.id)
    } else {
      setMessages([])
    }
  }, [activeConv?.id])

  // Scroll to bottom on new message or history change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 3. Authenticated WebSocket Connection Management
  useEffect(() => {
    if (!activeConv) {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setWsStatus('disconnected')
      return
    }

    let isMounted = true

    const connectWebSocket = () => {
      if (wsRef.current) {
        wsRef.current.close()
      }

      setWsStatus('connecting')

      const token = localStorage.getItem('access_token') || ''
      const wsBase = import.meta.env.VITE_WS_BASE_URL || 'ws://127.0.0.1:8000'
      const wsUrl = `${wsBase}/ws/chats/${activeConv.id}${token ? `?token=${token}` : ''}`

      const socket = new WebSocket(wsUrl)
      wsRef.current = socket

      socket.onopen = () => {
        if (!isMounted) return
        setWsStatus('connected')
        // Re-sync messages in case any were delivered during reconnect
        loadMessages(activeConv.id)
      }

      socket.onmessage = (event) => {
        if (!isMounted) return
        try {
          const payload = JSON.parse(event.data)
          if (payload.type === 'new_message' && payload.message) {
            const newMsg = payload.message
            const isFromMe = Boolean(
              user?.id && String(newMsg.sender_id).toLowerCase() === String(user.id).toLowerCase()
            )
            const isForActiveChat = activeConv && newMsg.conversation_id === activeConv.id

            if (isForActiveChat) {
              setMessages((prev) => {
                // If real message already exists, do not duplicate
                if (prev.some((m) => m.id === newMsg.id)) return prev

                // If sent by me, reconcile with existing optimistic message
                if (isFromMe) {
                  const tempIndex = prev.findIndex(
                    (m) =>
                      String(m.id).startsWith('temp-') &&
                      m.content === newMsg.content &&
                      String(m.sender_id).toLowerCase() === String(newMsg.sender_id).toLowerCase()
                  )
                  if (tempIndex !== -1) {
                    const next = [...prev]
                    next[tempIndex] = { ...newMsg, is_mine: true }
                    return next
                  }
                }

                return [
                  ...prev,
                  {
                    ...newMsg,
                    is_mine: isFromMe,
                  },
                ]
              })

              // If it's an incoming message while we're actively looking at this chat, mark it read!
              if (!isFromMe) {
                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                  wsRef.current.send(JSON.stringify({ type: 'mark_read' }))
                } else {
                  markChatAsRead(activeConv.id).catch(() => {})
                }
              }
            }

            // Update conversation snippet and unread counter in sidebar list
            setConversations((prev) =>
              prev.map((c) => {
                if (c.id === newMsg.conversation_id) {
                  if (c.last_message?.id === newMsg.id) return c
                  const isActive = activeConv && activeConv.id === c.id
                  const newUnread = isActive || isFromMe ? 0 : (c.unread_count || 0) + 1
                  return {
                    ...c,
                    last_message: {
                      ...newMsg,
                      is_mine: isFromMe,
                    },
                    unread_count: newUnread,
                    updated_at: newMsg.created_at,
                  }
                }
                return c
              })
            )
          }

          // Handle real-time read receipt updates
          if (payload.type === 'messages_read' && payload.conversation_id === activeConv.id) {
            setMessages((prev) =>
              prev.map((m) => {
                const isMine = Boolean(
                  m.is_mine === true ||
                  (user?.id && String(m.sender_id).toLowerCase() === String(user.id).toLowerCase())
                )
                return isMine ? { ...m, is_read: true } : m
              })
            )
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err)
        }
      }

      socket.onerror = (err) => {
        console.warn('WebSocket error:', err)
      }

      socket.onclose = (event) => {
        if (!isMounted) return
        setWsStatus('disconnected')

        // Auto-reconnect after 3 seconds if conversation is still open
        if (event.code !== 1008) {
          reconnectTimeoutRef.current = setTimeout(() => {
            if (isMounted && activeConv) {
              connectWebSocket()
            }
          }, 3000)
        }
      }
    }

    connectWebSocket()

    return () => {
      isMounted = false
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [activeConv?.id, user?.id])

  // 4. Handle Sending a Message (Optimistic UI for Instant 0ms Feedback)
  const handleSendMessage = async (e) => {
    e.preventDefault()
    const content = inputText.trim()
    if (!content || !activeConv) return

    // 1. Immediately clear input field
    setInputText('')

    // 2. Generate optimistic message for zero-latency screen display
    const tempId = `temp-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`
    const nowIso = new Date().toISOString()
    const optimisticMsg = {
      id: tempId,
      conversation_id: activeConv.id,
      sender_id: user?.id,
      sender_name: user?.full_name,
      content: content,
      created_at: nowIso,
      is_read: false,
      is_mine: true,
      pending: true,
    }

    // 3. Immediately render in messages feed (0ms delay!)
    setMessages((prev) => [...prev, optimisticMsg])

    // 4. Immediately update sidebar snippet & move chat to top
    setConversations((prev) => {
      const updated = prev.map((c) => {
        if (c.id === activeConv.id) {
          return {
            ...c,
            last_message: {
              ...optimisticMsg,
              is_mine: true,
            },
            updated_at: nowIso,
          }
        }
        return c
      })
      return [...updated].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
    })

    // 5. Send via WebSocket (or fallback REST)
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ content, temp_id: tempId }))
    } else {
      try {
        const savedMsg = await sendMessageRest(activeConv.id, content)
        setMessages((prev) =>
          prev.map((m) => (m.id === tempId ? { ...savedMsg, is_mine: true } : m))
        )
      } catch (err) {
        console.error('Failed to send message via REST:', err)
        setMessages((prev) =>
          prev.map((m) => (m.id === tempId ? { ...m, failed: true } : m))
        )
      }
    }
  }

  // Switch Conversation
  const handleSelectConv = (conv) => {
    setActiveConv(conv)
    setSearchParams({ id: conv.id })
    setShowMobileList(false)
    // Clear unread badge locally for the opened conversation
    setConversations((prev) =>
      prev.map((c) => (c.id === conv.id ? { ...c, unread_count: 0 } : c))
    )
  }

  return (
    <div className="chat-container">
      {/* SIDEBAR: CONVERSATIONS LIST */}
      <aside className={`chat-sidebar ${!showMobileList ? 'mobile-hidden' : ''}`}>
        <div className="sidebar-header">
          <h2>💬 Conversations</h2>
          <button
            type="button"
            className="button button-outline btn-sm"
            onClick={() => navigate('/dashboard')}
          >
            + New
          </button>
        </div>

        {loadingChats ? (
          <div className="sidebar-empty">Loading chats...</div>
        ) : conversations.length === 0 ? (
          <div className="sidebar-empty">
            <p>No conversations yet.</p>
            <small>Go to Dashboard and search an email to start chatting!</small>
          </div>
        ) : (
          <div className="conversation-items">
            {conversations.map((c) => {
              const other = c.other_participant
              const isSelected = activeConv?.id === c.id
              return (
                <div
                  key={c.id}
                  className={`conv-item ${isSelected ? 'active' : ''}`}
                  onClick={() => handleSelectConv(c)}
                >
                  <div className="conv-avatar">
                    {other?.display_name?.charAt(0).toUpperCase()}
                  </div>
                  <div className="conv-meta">
                    <div className="conv-title-row">
                      <h4>{other?.display_name}</h4>
                      {c.last_message && (
                        <span className="conv-time">
                          {new Date(c.last_message.created_at).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                      )}
                    </div>
                    {other?.display_name !== other?.original_name && (
                      <span className="contact-tag">Alias: {other?.display_name}</span>
                    )}
                    <div className="conv-subtitle-row">
                      <p className="conv-preview">
                        {c.last_message
                          ? `${c.last_message.is_mine ? 'You: ' : ''}${c.last_message.content}`
                          : 'No messages yet'}
                      </p>
                      {c.unread_count > 0 && (
                        <span className="unread-badge" title={`${c.unread_count} unread messages`}>
                          {c.unread_count}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </aside>

      {/* MAIN: CHAT WINDOW */}
      <section className={`chat-window ${showMobileList ? 'mobile-hidden' : ''}`}>
        {activeConv ? (
          <>
            {/* Chat Window Header */}
            <header className="chat-header">
              <button
                type="button"
                className="mobile-back-btn"
                onClick={handleMobileBack}
                aria-label="Back to conversations"
              >
                ←
              </button>
              <div className="header-avatar">
                {activeConv.other_participant?.display_name?.charAt(0).toUpperCase()}
              </div>
              <div className="header-info">
                <h3>{activeConv.other_participant?.display_name}</h3>
                <span className="header-sub">
                  {activeConv.other_participant?.email}
                  {activeConv.other_participant?.display_name !== activeConv.other_participant?.original_name && (
                    <> • (Original: {activeConv.other_participant?.original_name})</>
                  )}
                </span>
              </div>
              <div className="ws-status-badge">
                {wsStatus === 'connected' && (
                  <span className="badge badge-success">🟢 Live</span>
                )}
                {wsStatus === 'connecting' && (
                  <span className="badge badge-pending">🟡 Connecting...</span>
                )}
                {wsStatus === 'disconnected' && (
                  <span className="badge badge-error">🔴 Reconnecting...</span>
                )}
              </div>
            </header>

            {/* Messages Feed */}
            <div className="messages-feed">
              {loadingMessages ? (
                <div className="messages-empty">Loading message history...</div>
              ) : messages.length === 0 ? (
                <div className="messages-empty">
                  <div className="empty-chat-icon">👋</div>
                  <h4>No messages here yet</h4>
                  <p>Send a message below to start your private conversation with {activeConv.other_participant?.display_name}!</p>
                </div>
              ) : (
                messages.map((m) => {
                  const isMine = Boolean(
                    m.is_mine === true ||
                    (user?.id && String(m.sender_id).toLowerCase() === String(user.id).toLowerCase())
                  )
                  return (
                    <div
                      key={m.id}
                      className={`message-bubble-row ${isMine ? 'outgoing' : 'incoming'}`}
                    >
                      <div className={`message-bubble ${isMine ? 'bubble-outgoing' : 'bubble-incoming'}`}>
                        {!isMine && (
                          <div className="message-sender-label">
                            {activeConv.other_participant?.display_name || m.sender_name}
                          </div>
                        )}
                        <div className="message-text">{m.content}</div>
                        <div className="message-meta">
                          <span className="message-time">
                            {new Date(m.created_at).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                          {isMine && (
                            <span
                              className={`message-ticks ${m.is_read ? 'ticks-read' : 'ticks-sent'}`}
                              title={m.is_read ? 'Seen' : 'Sent'}
                            >
                              {m.is_read ? '✓✓' : '✓'}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input & Send Form */}
            <form onSubmit={handleSendMessage} className="chat-input-form">
              <input
                type="text"
                placeholder="Type a message..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                autoFocus
              />
              <button
                type="submit"
                className="button button-primary send-btn"
                disabled={!inputText.trim()}
              >
                Send 🚀
              </button>
            </form>
          </>
        ) : (
          <div className="no-chat-selected">
            <div className="empty-icon">💬</div>
            <h3>Your Private Messages</h3>
            <p>Select an existing conversation from the left, or visit the Dashboard to search for a user and start a new conversation.</p>
            <button
              type="button"
              className="button button-primary"
              onClick={() => navigate('/dashboard')}
              style={{ marginTop: '1rem', width: 'auto' }}
            >
              Go to Dashboard
            </button>
          </div>
        )}
      </section>
    </div>
  )
}

