import React, { useState, useEffect, useRef, useMemo } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  getChatsList,
  getChatMessages,
  sendMessageRest,
  editMessageRest,
  deleteMessageRest,
  toggleReactionRest,
  markChatAsRead,
} from '../api/chats'
import AudioMessagePlayer from '../components/AudioMessagePlayer'
import EmojiPicker from '../components/EmojiPicker'
import MessageReactionBar from '../components/MessageReactionBar'
import VoiceRecorderBar from '../components/VoiceRecorderBar'

// LocalStorage helpers for 0ms instant loading
const CONV_CACHE_KEY = (uid) => `chat_conversations_v2_${uid || 'me'}`
const MSG_CACHE_KEY = (convId) => `chat_messages_v2_${convId}`

const getStoredConvs = (uid) => {
  try {
    const raw = localStorage.getItem(CONV_CACHE_KEY(uid))
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

const saveStoredConvs = (uid, list) => {
  if (!Array.isArray(list)) return
  try {
    localStorage.setItem(CONV_CACHE_KEY(uid), JSON.stringify(list))
  } catch {}
}

const getStoredMessages = (convId) => {
  if (!convId) return null
  try {
    const raw = localStorage.getItem(MSG_CACHE_KEY(convId))
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

const saveStoredMessages = (convId, list) => {
  if (!convId || !Array.isArray(list)) return
  try {
    const clean = list.slice(-100).filter((m) => !String(m.id).startsWith('temp-'))
    localStorage.setItem(MSG_CACHE_KEY(convId), JSON.stringify(clean))
  } catch (e) {
    try {
      const keys = Object.keys(localStorage).filter((k) => k.startsWith('chat_messages_v2_'))
      if (keys.length > 30) {
        keys.slice(0, 15).forEach((k) => localStorage.removeItem(k))
      }
    } catch {}
  }
}

export default function Chat() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const targetConvId = searchParams.get('id')
  const initialCachedConvs = useMemo(() => getStoredConvs(user?.id), [user?.id])
  const initialTargetConv = useMemo(() => {
    if (!targetConvId) return null
    return initialCachedConvs.find((c) => c.id === targetConvId) || null
  }, [targetConvId, initialCachedConvs])
  const initialCachedMsgs = useMemo(() => {
    return initialTargetConv ? (getStoredMessages(initialTargetConv.id) || []) : []
  }, [initialTargetConv])

  const [conversations, setConversations] = useState(initialCachedConvs)
  const [loadingChats, setLoadingChats] = useState(initialCachedConvs.length === 0)
  const [activeConv, setActiveConv] = useState(initialTargetConv)

  const [messages, setMessages] = useState(initialCachedMsgs)
  const [loadingMessages, setLoadingMessages] = useState(
    Boolean(initialTargetConv && initialCachedMsgs.length === 0)
  )
  const [inputText, setInputText] = useState('')

  // Advanced features states
  const [isRecording, setIsRecording] = useState(false)
  const [showEmojiPicker, setShowEmojiPicker] = useState(false)
  const [typingMap, setTypingMap] = useState({}) // { [convId]: { isTyping: bool, userName: str } }
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [currentSearchIdx, setCurrentSearchIdx] = useState(0)

  // Message edit & delete modals/state
  const [activeReactionMsgId, setActiveReactionMsgId] = useState(null)
  const [activeMenuMsgId, setActiveMenuMsgId] = useState(null)
  const [menuDirection, setMenuDirection] = useState('up') // 'up' | 'down'
  const [editingMessage, setEditingMessage] = useState(null) // { id: str, content: str }

  // WebSocket state
  const [wsStatus, setWsStatus] = useState('disconnected') // 'connecting' | 'connected' | 'disconnected'
  const wsRef = useRef(null)
  const userWsRef = useRef(null)
  const activeConvRef = useRef(null)
  const messagesEndRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const userReconnectTimeoutRef = useRef(null)
  const typingTimeoutRef = useRef(null)
  const isTypingLocalRef = useRef(false)
  const messageItemRefs = useRef({})
  const longPressTimerRef = useRef(null)

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

  // Close menus when clicking anywhere outside
  useEffect(() => {
    const handleGlobalClick = () => {
      setActiveReactionMsgId(null)
      setActiveMenuMsgId(null)
    }
    window.addEventListener('click', handleGlobalClick)
    return () => window.removeEventListener('click', handleGlobalClick)
  }, [])

  // Long press handler (press and hold message bubble to open reactions)
  const startLongPress = (msgId) => {
    if (longPressTimerRef.current) clearTimeout(longPressTimerRef.current)
    longPressTimerRef.current = setTimeout(() => {
      setActiveReactionMsgId(msgId)
      setActiveMenuMsgId(null)
      if (typeof navigator !== 'undefined' && navigator.vibrate) {
        try {
          navigator.vibrate(50)
        } catch (e) {}
      }
    }, 450)
  }

  const cancelLongPress = () => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current)
      longPressTimerRef.current = null
    }
  }

  // Format Last Seen Time
  const formatLastSeen = (lastSeenAt) => {
    if (!lastSeenAt) return 'Offline'
    try {
      const date = new Date(lastSeenAt)
      if (isNaN(date.getTime())) return 'Offline'
      const now = new Date()
      const isToday = date.toDateString() === now.toDateString()
      const yesterday = new Date(now)
      yesterday.setDate(now.getDate() - 1)
      const isYesterday = date.toDateString() === yesterday.toDateString()
      const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      if (isToday) return `Last seen today at ${timeStr}`
      if (isYesterday) return `Last seen yesterday at ${timeStr}`
      return `Last seen on ${date.toLocaleDateString([], { month: 'short', day: 'numeric' })} at ${timeStr}`
    } catch {
      return 'Offline'
    }
  }

  // Keep cached conversations updated in localStorage whenever conversations change
  useEffect(() => {
    if (conversations && conversations.length > 0) {
      saveStoredConvs(user?.id, conversations)
    }
  }, [conversations, user?.id])

  // Hydrate from localStorage once user?.id is resolved if initial state was empty
  useEffect(() => {
    if (user?.id && conversations.length === 0) {
      const stored = getStoredConvs(user.id)
      if (stored && stored.length > 0) {
        setConversations(stored)
        setLoadingChats(false)
        const targetId = searchParams.get('id')
        if (targetId && !activeConvRef.current) {
          const found = stored.find((c) => c.id === targetId)
          if (found) {
            setActiveConv(found)
            const msgs = getStoredMessages(found.id)
            if (msgs) {
              setMessages(msgs)
              setLoadingMessages(false)
            }
          }
        }
      }
    }
  }, [user?.id])

  // 1. Fetch Conversations List
  const loadConversations = async (silent = false) => {
    try {
      const data = await getChatsList()
      saveStoredConvs(user?.id, data)
      setConversations((prev) => {
        const currentActiveId = activeConvRef.current?.id
        return data.map((conv) => {
          if (conv.id === currentActiveId) {
            return { ...conv, unread_count: 0 }
          }
          return conv
        })
      })

      // Warm the message cache for recent chats so they open in 0ms!
      data.slice(0, 10).forEach((c) => prefetchMessages(c.id))

      if (!silent) {
        const targetId = searchParams.get('id')
        if (targetId) {
          const found = data.find((c) => c.id === targetId)
          if (found && !activeConvRef.current) {
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
    const pollInterval = setInterval(() => {
      loadConversations(true)
    }, 4000)
    return () => clearInterval(pollInterval)
  }, [])

  // 1b. User-Level Real-Time Stream (sidebar updates, typing, user presence)
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

          // User presence status
          if (payload.type === 'user_status') {
            const { user_id, is_online, last_seen_at } = payload
            setConversations((prev) =>
              prev.map((c) => {
                if (c.other_participant?.id === user_id) {
                  return {
                    ...c,
                    other_participant: {
                      ...c.other_participant,
                      is_online,
                      last_seen_at: last_seen_at || c.other_participant.last_seen_at,
                    },
                  }
                }
                return c
              })
            )
            setActiveConv((prev) => {
              if (prev && prev.other_participant?.id === user_id) {
                return {
                  ...prev,
                  other_participant: {
                    ...prev.other_participant,
                    is_online,
                    last_seen_at: last_seen_at || prev.other_participant.last_seen_at,
                  },
                }
              }
              return prev
            })
          }

          // Real-time new message preview in sidebar
          if (payload.type === 'new_message' && payload.message) {
            const newMsg = payload.message
            const isFromMe = Boolean(
              user?.id && String(newMsg.sender_id).toLowerCase() === String(user.id).toLowerCase()
            )
            const currentActiveId = activeConvRef.current?.id

            // Also update the cached messages for this conversation so it opens with this new message in 0ms
            const convId = newMsg.conversation_id
            const existingCache = messagesCacheRef.current[convId] || getStoredMessages(convId)
            if (existingCache && Array.isArray(existingCache)) {
              if (!existingCache.some((m) => m.id === newMsg.id)) {
                const updatedCache = [...existingCache, newMsg]
                messagesCacheRef.current[convId] = updatedCache
                saveStoredMessages(convId, updatedCache)
              }
            }

            setConversations((prev) => {
              const exists = prev.some((c) => c.id === newMsg.conversation_id)
              if (!exists) {
                loadConversations(true)
                return prev
              }

              const updated = prev.map((c) => {
                if (c.id === newMsg.conversation_id) {
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
  // In-memory + LocalStorage cache so opening any chat shows messages in 0ms (instant appearance)
  const messagesCacheRef = useRef({})
  const prefetchingRef = useRef(new Set())

  const prefetchMessages = (conversationId) => {
    if (messagesCacheRef.current[conversationId] || prefetchingRef.current.has(conversationId)) return
    const stored = getStoredMessages(conversationId)
    if (stored && stored.length > 0) {
      messagesCacheRef.current[conversationId] = stored
      return
    }
    prefetchingRef.current.add(conversationId)
    getChatMessages(conversationId)
      .then((res) => {
        const list = res.messages || []
        messagesCacheRef.current[conversationId] = list
        saveStoredMessages(conversationId, list)
      })
      .catch(() => {})
      .finally(() => prefetchingRef.current.delete(conversationId))
  }

  const loadMessages = async (conversationId) => {
    const cached = messagesCacheRef.current[conversationId] || getStoredMessages(conversationId)
    if (cached && cached.length > 0) {
      messagesCacheRef.current[conversationId] = cached
      if (activeConvRef.current?.id === conversationId) {
        setMessages(cached)
        setLoadingMessages(false)
      }
    } else if (activeConvRef.current?.id === conversationId) {
      setLoadingMessages(true)
    }

    try {
      const res = await getChatMessages(conversationId)
      const list = res.messages || []
      messagesCacheRef.current[conversationId] = list
      saveStoredMessages(conversationId, list)

      // Only apply if user is still viewing this conversation
      if (activeConvRef.current?.id === conversationId) {
        setMessages(list)
      }

      const hasUnread = list.some((m) => !m.is_mine && !m.is_read)
      if (hasUnread) {
        markChatAsRead(conversationId).catch(() => {})
      }
    } catch (err) {
      console.error('Failed to load messages:', err)
    } finally {
      if (activeConvRef.current?.id === conversationId) setLoadingMessages(false)
    }
  }

  useEffect(() => {
    if (activeConv) {
      loadMessages(activeConv.id)
    } else {
      setMessages([])
    }
  }, [activeConv?.id])

  // Keep cache in sync with live changes (new/edited/deleted/reacted messages)
  useEffect(() => {
    const id = activeConv?.id
    if (!id || loadingMessages) return
    if (messages.length === 0 || messages[0]?.conversation_id === id) {
      const cleanList = messages.filter((m) => !String(m.id).startsWith('temp'))
      messagesCacheRef.current[id] = cleanList
      saveStoredMessages(id, cleanList)
    }
  }, [messages, activeConv?.id, loadingMessages])

  // Auto-scroll to bottom on new message
  useEffect(() => {
    if (!isSearching) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isSearching])

  // 3. Authenticated Active Conversation WebSocket
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
        loadMessages(activeConv.id)
      }

      socket.onmessage = (event) => {
        if (!isMounted) return
        try {
          const payload = JSON.parse(event.data)

          // 1. Typing indicator
          if (payload.type === 'typing') {
            const { conversation_id, user_id, user_name, is_typing } = payload
            if (user?.id && String(user_id).toLowerCase() !== String(user.id).toLowerCase()) {
              setTypingMap((prev) => ({
                ...prev,
                [conversation_id]: { isTyping: is_typing, userName: user_name },
              }))
            }
          }

          // 2. New message
          if (payload.type === 'new_message' && payload.message) {
            const newMsg = payload.message
            const isFromMe = Boolean(
              user?.id && String(newMsg.sender_id).toLowerCase() === String(user.id).toLowerCase()
            )
            const isForActiveChat = activeConv && newMsg.conversation_id === activeConv.id

            if (isForActiveChat) {
              setMessages((prev) => {
                if (prev.some((m) => m.id === newMsg.id)) return prev

                if (isFromMe) {
                  const tempIndex = prev.findIndex(
                    (m) =>
                      String(m.id).startsWith('temp-') &&
                      (m.content === newMsg.content || m.media_url === newMsg.media_url)
                  )
                  if (tempIndex !== -1) {
                    const next = [...prev]
                    next[tempIndex] = { ...newMsg, is_mine: true }
                    return next
                  }
                }

                return [...prev, { ...newMsg, is_mine: isFromMe }]
              })

              if (!isFromMe) {
                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                  wsRef.current.send(JSON.stringify({ type: 'mark_read' }))
                } else {
                  markChatAsRead(activeConv.id).catch(() => {})
                }
              }
            }

            // Update sidebar
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

          // 3. Message read receipts
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

          // 4. Message Edited
          if (payload.type === 'message_edited') {
            const { message_id, content, is_edited, edited_at } = payload
            setMessages((prev) =>
              prev.map((m) =>
                m.id === message_id ? { ...m, content, is_edited: true, edited_at } : m
              )
            )
          }

          // 5. Message Deleted
          if (payload.type === 'message_deleted') {
            const { message_id, delete_type, deleted_by_user_id, is_deleted_everyone, content } = payload
            const isMe = user?.id && String(deleted_by_user_id).toLowerCase() === String(user.id).toLowerCase()

            setMessages((prev) => {
              if (delete_type === 'me' && isMe) {
                return prev.filter((m) => m.id !== message_id)
              }
              if (is_deleted_everyone) {
                return prev.map((m) =>
                  m.id === message_id
                    ? {
                        ...m,
                        content: content || '🚫 This message was deleted',
                        media_url: null,
                        is_deleted_everyone: true,
                      }
                    : m
                )
              }
              return prev
            })
          }

          // 6. Message Reaction
          if (payload.type === 'message_reaction') {
            const { message_id, reactions } = payload
            setMessages((prev) =>
              prev.map((m) => (m.id === message_id ? { ...m, reactions } : m))
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

  // Typing emitter handler
  const handleInputChange = (e) => {
    const val = e.target.value
    setInputText(val)

    if (!activeConv || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return

    if (!isTypingLocalRef.current) {
      isTypingLocalRef.current = true
      wsRef.current.send(JSON.stringify({ type: 'typing', is_typing: true }))
    }

    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current)
    typingTimeoutRef.current = setTimeout(() => {
      isTypingLocalRef.current = false
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'typing', is_typing: false }))
      }
    }, 2000)
  }

  // 4. Send Message (Text)
  const handleSendMessage = async (e) => {
    if (e) e.preventDefault()
    const content = inputText.trim()
    if (!content || !activeConv) return

    setInputText('')
    setShowEmojiPicker(false)

    // Stop typing state immediately
    if (isTypingLocalRef.current) {
      isTypingLocalRef.current = false
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'typing', is_typing: false }))
      }
    }

    const tempId = `temp-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`
    const nowIso = new Date().toISOString()
    const optimisticMsg = {
      id: tempId,
      conversation_id: activeConv.id,
      sender_id: user?.id,
      sender_name: user?.full_name,
      content: content,
      message_type: 'text',
      created_at: nowIso,
      is_read: false,
      is_mine: true,
      pending: true,
    }

    setMessages((prev) => [...prev, optimisticMsg])

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

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ content, message_type: 'text', temp_id: tempId }))
    } else {
      try {
        const savedMsg = await sendMessageRest(activeConv.id, content, 'text')
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

  // 5. Send Audio Message (Voice Note)
  const handleSendAudio = async (base64AudioData, durationSecs) => {
    if (!activeConv || !base64AudioData) return
    setIsRecording(false)

    const tempId = `temp-audio-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`
    const nowIso = new Date().toISOString()
    const optimisticAudioMsg = {
      id: tempId,
      conversation_id: activeConv.id,
      sender_id: user?.id,
      sender_name: user?.full_name,
      content: '🎙️ Voice note',
      message_type: 'audio',
      media_url: base64AudioData,
      media_duration: durationSecs,
      created_at: nowIso,
      is_read: false,
      is_mine: true,
      pending: true,
    }

    setMessages((prev) => [...prev, optimisticAudioMsg])

    setConversations((prev) => {
      const updated = prev.map((c) => {
        if (c.id === activeConv.id) {
          return {
            ...c,
            last_message: {
              ...optimisticAudioMsg,
              is_mine: true,
            },
            updated_at: nowIso,
          }
        }
        return c
      })
      return [...updated].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
    })

    const payload = {
      content: '🎙️ Voice note',
      message_type: 'audio',
      media_url: base64AudioData,
      media_duration: durationSecs,
      temp_id: tempId,
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload))
    } else {
      try {
        const saved = await sendMessageRest(
          activeConv.id,
          '🎙️ Voice note',
          'audio',
          base64AudioData,
          durationSecs
        )
        setMessages((prev) =>
          prev.map((m) => (m.id === tempId ? { ...saved, is_mine: true } : m))
        )
      } catch (err) {
        console.error('Failed to send voice note via REST:', err)
        setMessages((prev) =>
          prev.map((m) => (m.id === tempId ? { ...m, failed: true } : m))
        )
      }
    }
  }

  // 6. Handle Reaction with Optimistic 0ms UI Feedback
  const handleToggleReaction = async (messageId, emoji) => {
    if (!activeConv) return
    setActiveReactionMsgId(null)

    const myUidStr = String(user?.id)
    const myName = user?.full_name || 'You'

    // Optimistic update
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== messageId) return m

        const currentReactions = Array.isArray(m.reactions) ? [...m.reactions] : []
        const alreadyHadSame = currentReactions.some(
          (r) => String(r.user_id) === myUidStr && r.emoji === emoji
        )

        const filtered = currentReactions.filter((r) => String(r.user_id) !== myUidStr)
        if (!alreadyHadSame && emoji !== 'remove') {
          filtered.push({
            emoji,
            user_id: myUidStr,
            user_name: myName,
          })
        }

        return { ...m, reactions: filtered }
      })
    )

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'reaction', message_id: messageId, emoji }))
    } else {
      try {
        const updated = await toggleReactionRest(activeConv.id, messageId, emoji)
        setMessages((prev) =>
          prev.map((m) => (m.id === messageId ? { ...m, reactions: updated.reactions } : m))
        )
      } catch (err) {
        console.error('Reaction failed:', err)
      }
    }
  }

  // 7. Handle Edit Message Submit
  const handleSaveEdit = async () => {
    if (!editingMessage || !editingMessage.content.trim() || !activeConv) return
    const { id, content } = editingMessage

    // Optimistic local update
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, content: content.trim(), is_edited: true } : m))
    )

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: 'edit_message', message_id: id, content: content.trim() })
      )
    } else {
      try {
        await editMessageRest(activeConv.id, id, content.trim())
      } catch (err) {
        console.error('Edit failed:', err)
      }
    }
    setEditingMessage(null)
  }

  // 8. Handle Delete Message Submit (Direct from 3-dots menu)
  const handleExecuteDelete = async (deleteType, messageId) => {
    if (!messageId || !activeConv) return

    if (deleteType === 'everyone') {
      const ok = window.confirm('Are you sure you want to delete this message for everyone?')
      if (!ok) return
    }

    if (deleteType === 'me') {
      setMessages((prev) => prev.filter((m) => m.id !== messageId))
    } else {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? { ...m, content: '🚫 This message was deleted', media_url: null, is_deleted_everyone: true }
            : m
        )
      )
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: 'delete_message', message_id: messageId, delete_type: deleteType })
      )
    } else {
      try {
        await deleteMessageRest(activeConv.id, messageId, deleteType)
      } catch (err) {
        console.error('Delete failed:', err)
      }
    }
  }

  // Search matches
  const searchMatches = useMemo(() => {
    if (!searchQuery.trim()) return []
    const q = searchQuery.toLowerCase()
    const matches = []
    messages.forEach((m, idx) => {
      if (m.content && m.content.toLowerCase().includes(q)) {
        matches.push({ index: idx, id: m.id })
      }
    })
    return matches
  }, [messages, searchQuery])

  useEffect(() => {
    if (searchMatches.length > 0) {
      setCurrentSearchIdx(0)
      scrollToMatch(searchMatches[0]?.id)
    }
  }, [searchMatches])

  const scrollToMatch = (msgId) => {
    if (!msgId) return
    const el = messageItemRefs.current[msgId]
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }

  const handleNextSearchMatch = () => {
    if (searchMatches.length === 0) return
    const nextIdx = (currentSearchIdx + 1) % searchMatches.length
    setCurrentSearchIdx(nextIdx)
    scrollToMatch(searchMatches[nextIdx]?.id)
  }

  const handlePrevSearchMatch = () => {
    if (searchMatches.length === 0) return
    const prevIdx = (currentSearchIdx - 1 + searchMatches.length) % searchMatches.length
    setCurrentSearchIdx(prevIdx)
    scrollToMatch(searchMatches[prevIdx]?.id)
  }

  // Helper to highlight matching text
  const renderMessageContent = (text, isDeleted) => {
    if (isDeleted) {
      return <span className="deleted-message-text">{text}</span>
    }
    if (!searchQuery.trim() || !text) return text

    const parts = text.split(new RegExp(`(${searchQuery.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&')})`, 'gi'))
    return parts.map((part, i) =>
      part.toLowerCase() === searchQuery.toLowerCase() ? (
        <mark key={i} className="search-highlight">
          {part}
        </mark>
      ) : (
        part
      )
    )
  }

  // Switch Conversation
  const handleSelectConv = (conv) => {
    // 0ms instant display of cached messages
    const cached = messagesCacheRef.current[conv.id] || getStoredMessages(conv.id)
    if (cached && cached.length > 0) {
      messagesCacheRef.current[conv.id] = cached
      setMessages(cached)
      setLoadingMessages(false)
    } else {
      setMessages([])
      setLoadingMessages(true)
    }

    setActiveConv(conv)
    setSearchParams({ id: conv.id })
    setShowMobileList(false)
    setIsSearching(false)
    setSearchQuery('')
    setActiveReactionMsgId(null)
    setActiveMenuMsgId(null)
    setConversations((prev) =>
      prev.map((c) => (c.id === conv.id ? { ...c, unread_count: 0 } : c))
    )
  }

  const isOtherTyping = activeConv && typingMap[activeConv.id]?.isTyping
  const otherParticipant = activeConv?.other_participant

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
              const isConvTyping = typingMap[c.id]?.isTyping
              const isUserOnline = other?.is_online

              return (
                <div
                  key={c.id}
                  className={`conv-item ${isSelected ? 'active' : ''}`}
                  onClick={() => handleSelectConv(c)}
                >
                  <div className="conv-avatar-wrapper">
                    <div className="conv-avatar">
                      {other?.display_name?.charAt(0).toUpperCase()}
                    </div>
                    {isUserOnline && <span className="avatar-online-dot" title="Online" />}
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

                    <div className="conv-subtitle-row">
                      {isConvTyping ? (
                        <p className="conv-typing-status">
                          <span className="typing-dots-anim">•••</span> typing...
                        </p>
                      ) : (
                        <p className="conv-preview">
                          {c.last_message ? (
                            <>
                              {c.last_message.is_mine ? 'You: ' : ''}
                              {c.last_message.message_type === 'audio'
                                ? '🎙️ Voice note'
                                : c.last_message.content}
                            </>
                          ) : (
                            'No messages yet'
                          )}
                        </p>
                      )}

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

              <div className="header-avatar-wrapper">
                <div className="header-avatar">
                  {otherParticipant?.display_name?.charAt(0).toUpperCase()}
                </div>
                {otherParticipant?.is_online && (
                  <span className="header-avatar-online-dot" title="Online" />
                )}
              </div>

              <div className="header-info">
                <h3>{otherParticipant?.display_name}</h3>
                <div className="header-status-line">
                  {isOtherTyping ? (
                    <span className="header-typing-indicator">
                      <span className="typing-pulse-dot" /> typing...
                    </span>
                  ) : otherParticipant?.is_online ? (
                    <span className="header-online-status">
                      <span className="online-green-dot" /> Online
                    </span>
                  ) : (
                    <span className="header-last-seen">
                      {formatLastSeen(otherParticipant?.last_seen_at)}
                    </span>
                  )}
                </div>
              </div>

              {/* In-Chat Search & Status Actions */}
              <div className="chat-header-actions">
                <button
                  type="button"
                  className={`chat-header-btn ${isSearching ? 'active' : ''}`}
                  onClick={() => {
                    setIsSearching((prev) => !prev)
                    if (isSearching) setSearchQuery('')
                  }}
                  title="Search messages in this chat"
                >
                  🔍
                </button>

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
              </div>
            </header>

            {/* In-Chat Search Bar Drawer */}
            {isSearching && (
              <div className="in-chat-search-bar">
                <span className="search-icon-prefix">🔍</span>
                <input
                  type="text"
                  placeholder="Search in conversation..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  autoFocus
                />
                {searchQuery.trim() && (
                  <span className="search-match-count">
                    {searchMatches.length > 0
                      ? `${currentSearchIdx + 1} of ${searchMatches.length}`
                      : 'No matches'}
                  </span>
                )}
                <button
                  type="button"
                  className="search-nav-btn"
                  onClick={handlePrevSearchMatch}
                  disabled={searchMatches.length === 0}
                  title="Previous match"
                >
                  ▲
                </button>
                <button
                  type="button"
                  className="search-nav-btn"
                  onClick={handleNextSearchMatch}
                  disabled={searchMatches.length === 0}
                  title="Next match"
                >
                  ▼
                </button>
                <button
                  type="button"
                  className="search-close-btn"
                  onClick={() => {
                    setIsSearching(false)
                    setSearchQuery('')
                  }}
                  title="Close search"
                >
                  ✕
                </button>
              </div>
            )}

            {/* Messages Feed */}
            <div className="messages-feed">
              {loadingMessages ? (
                <div className="messages-empty">Loading message history...</div>
              ) : messages.length === 0 ? (
                <div className="messages-empty">
                  <div className="empty-chat-icon">👋</div>
                  <h4>No messages here yet</h4>
                  <p>
                    Send a message or voice note below to start your conversation with{' '}
                    {otherParticipant?.display_name}!
                  </p>
                </div>
              ) : (
                messages.map((m) => {
                  const isMine = Boolean(
                    m.is_mine === true ||
                    (user?.id && String(m.sender_id).toLowerCase() === String(user.id).toLowerCase())
                  )
                  const isReactionOpen = activeReactionMsgId === m.id
                  const isMenuOpen = activeMenuMsgId === m.id
                  const isEditingThis = editingMessage?.id === m.id
                  const isDeleted = m.is_deleted_everyone

                  // Group reactions by emoji
                  const reactionCounts = {}
                  let myCurrentEmoji = null
                  if (m.reactions && Array.isArray(m.reactions)) {
                    m.reactions.forEach((r) => {
                      if (!reactionCounts[r.emoji]) {
                        reactionCounts[r.emoji] = { count: 0, hasMine: false, users: [] }
                      }
                      reactionCounts[r.emoji].count += 1
                      reactionCounts[r.emoji].users.push(r.user_name || 'Someone')
                      if (user?.id && String(r.user_id) === String(user.id)) {
                        reactionCounts[r.emoji].hasMine = true
                        myCurrentEmoji = r.emoji
                      }
                    })
                  }

                  return (
                    <div
                      key={m.id}
                      ref={(el) => (messageItemRefs.current[m.id] = el)}
                      className={`message-bubble-row ${isMine ? 'outgoing' : 'incoming'} ${
                        isMenuOpen || isReactionOpen ? 'has-active-popup' : ''
                      }`}
                    >
                      {/* Floating Quick Reaction Bar (Triggered on Press & Hold / Double Click / Menu) */}
                      {!isDeleted && isReactionOpen && (
                        <MessageReactionBar
                          currentReaction={myCurrentEmoji}
                          onReact={(emoji) => handleToggleReaction(m.id, emoji)}
                          onClose={() => setActiveReactionMsgId(null)}
                        />
                      )}

                      <div
                        className={`message-bubble ${isMine ? 'bubble-outgoing' : 'bubble-incoming'} ${
                          isDeleted ? 'bubble-deleted' : ''
                        } ${isMenuOpen || isReactionOpen ? 'has-active-popup' : ''}`}
                        onMouseDown={() => startLongPress(m.id)}
                        onMouseUp={cancelLongPress}
                        onMouseLeave={cancelLongPress}
                        onTouchStart={() => startLongPress(m.id)}
                        onTouchEnd={cancelLongPress}
                        onTouchMove={cancelLongPress}
                        onContextMenu={(e) => {
                          e.preventDefault()
                          setActiveReactionMsgId(m.id)
                          setActiveMenuMsgId(null)
                        }}
                        onDoubleClick={() => {
                          setActiveReactionMsgId(m.id)
                        }}
                      >
                        {!isMine && (
                          <div className="message-sender-label">
                            {otherParticipant?.display_name || m.sender_name}
                          </div>
                        )}

                        {/* Inline Edit Mode */}
                        {isEditingThis ? (
                          <div className="inline-edit-box">
                            <input
                              type="text"
                              value={editingMessage.content}
                              onChange={(e) =>
                                setEditingMessage({ ...editingMessage, content: e.target.value })
                              }
                              autoFocus
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleSaveEdit()
                                if (e.key === 'Escape') setEditingMessage(null)
                              }}
                            />
                            <div className="inline-edit-actions">
                              <button
                                type="button"
                                className="btn-edit-save"
                                onClick={handleSaveEdit}
                                title="Save changes"
                              >
                                ✓
                              </button>
                              <button
                                type="button"
                                className="btn-edit-cancel"
                                onClick={() => setEditingMessage(null)}
                                title="Cancel"
                              >
                                ✕
                              </button>
                            </div>
                          </div>
                        ) : m.message_type === 'audio' && m.media_url && !isDeleted ? (
                          /* Voice Note Message */
                          <AudioMessagePlayer
                            mediaUrl={m.media_url}
                            duration={m.media_duration}
                            isMine={isMine}
                          />
                        ) : (
                          /* Standard Text Message */
                          <div className="message-text">
                            {renderMessageContent(m.content, isDeleted)}
                          </div>
                        )}

                        {/* Message Meta (Time, Edited tag, Ticks, & 3-Dots Menu Button) */}
                        <div className="message-meta">
                          {m.is_edited && !isDeleted && (
                            <span className="edited-badge" title="Edited message">
                              (edited)
                            </span>
                          )}

                          <span className="message-time">
                            {new Date(m.created_at).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>

                          {isMine && !isDeleted && (
                            <span
                              className={`message-ticks ${m.is_read ? 'ticks-read' : 'ticks-sent'}`}
                              title={m.is_read ? 'Seen' : 'Sent'}
                            >
                              {m.is_read ? '✓✓' : '✓'}
                            </span>
                          )}

                          {/* 3-Dots Button on Right Bottom Corner */}
                          {!isDeleted && (
                            <div
                              className="msg-corner-menu-wrapper"
                              onClick={(e) => e.stopPropagation()}
                              onMouseDown={(e) => e.stopPropagation()}
                              onTouchStart={(e) => e.stopPropagation()}
                            >
                              <button
                                type="button"
                                className={`msg-corner-dots-btn ${isMenuOpen ? 'active' : ''}`}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  const btnRect = e.currentTarget.getBoundingClientRect()
                                  const feedEl = e.currentTarget.closest('.messages-feed')
                                  const feedRect = feedEl ? feedEl.getBoundingClientRect() : null
                                  const spaceAbove = feedRect ? btnRect.top - feedRect.top : btnRect.top
                                  setMenuDirection(spaceAbove > 190 ? 'up' : 'down')
                                  setActiveMenuMsgId(isMenuOpen ? null : m.id)
                                  setActiveReactionMsgId(null)
                                }}
                                title="Options"
                              >
                                ⋮
                              </button>

                              {isMenuOpen && (
                                <div className={`msg-corner-dropdown ${menuDirection === 'down' ? 'open-down' : 'open-up'}`}>
                                  {myCurrentEmoji ? (
                                    <button
                                      type="button"
                                      className="dropdown-item dropdown-item-danger"
                                      onClick={() => {
                                        handleToggleReaction(m.id, 'remove')
                                        setActiveMenuMsgId(null)
                                      }}
                                    >
                                      <span className="dropdown-icon-badge danger-badge">✕</span>
                                      <span className="dropdown-label">Remove React ({myCurrentEmoji})</span>
                                    </button>
                                  ) : (
                                    <button
                                      type="button"
                                      className="dropdown-item"
                                      onClick={() => {
                                        setActiveReactionMsgId(m.id)
                                        setActiveMenuMsgId(null)
                                      }}
                                    >
                                      <span className="dropdown-icon-badge">😊</span>
                                      <span className="dropdown-label">React</span>
                                    </button>
                                  )}

                                  {isMine && m.message_type === 'text' && (
                                    <button
                                      type="button"
                                      className="dropdown-item"
                                      onClick={() => {
                                        setEditingMessage({ id: m.id, content: m.content })
                                        setActiveMenuMsgId(null)
                                      }}
                                    >
                                      <span className="dropdown-icon-badge edit-badge">✏️</span>
                                      <span className="dropdown-label">Edit</span>
                                    </button>
                                  )}

                                  <div className="dropdown-divider" />

                                  {isMine && (
                                    <button
                                      type="button"
                                      className="dropdown-item dropdown-item-danger"
                                      onClick={() => {
                                        handleExecuteDelete('everyone', m.id)
                                        setActiveMenuMsgId(null)
                                      }}
                                    >
                                      <span className="dropdown-icon-badge danger-badge">🗑️</span>
                                      <span className="dropdown-label">Delete for everyone</span>
                                    </button>
                                  )}

                                  <button
                                    type="button"
                                    className="dropdown-item dropdown-item-danger"
                                    onClick={() => {
                                      handleExecuteDelete('me', m.id)
                                      setActiveMenuMsgId(null)
                                    }}
                                  >
                                    <span className="dropdown-icon-badge danger-badge">👤</span>
                                    <span className="dropdown-label">Delete for me</span>
                                  </button>
                                </div>
                              )}
                            </div>
                          )}
                        </div>

                        {/* Reaction Badges on Bubble */}
                        {Object.keys(reactionCounts).length > 0 && (
                          <div className="bubble-reactions-row">
                            {Object.entries(reactionCounts).map(([emoji, data]) => (
                              <button
                                key={emoji}
                                type="button"
                                className={`reaction-pill ${data.hasMine ? 'active' : ''}`}
                                onClick={() => handleToggleReaction(m.id, data.hasMine ? 'remove' : emoji)}
                                title={data.hasMine ? 'Click to remove your reaction' : data.users.join(', ')}
                              >
                                <span>{emoji}</span>
                                {data.count > 1 && <span className="r-count">{data.count}</span>}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input & Send Bar / Voice Recorder Bar */}
            <div className="chat-bottom-bar-wrapper">
              {showEmojiPicker && (
                <EmojiPicker
                  onSelectEmoji={(emoji) => setInputText((prev) => prev + emoji)}
                  onClose={() => setShowEmojiPicker(false)}
                />
              )}

              {isRecording ? (
                <VoiceRecorderBar
                  onSendAudio={handleSendAudio}
                  onCancel={() => setIsRecording(false)}
                />
              ) : (
                <form onSubmit={handleSendMessage} className="chat-input-bar">
                  {/* Emoji Trigger Button */}
                  <button
                    type="button"
                    className={`input-emoji-btn ${showEmojiPicker ? 'active' : ''}`}
                    onClick={() => setShowEmojiPicker((prev) => !prev)}
                    title="Insert emoji"
                  >
                    😊
                  </button>

                  {/* Text Input Pill */}
                  <input
                    type="text"
                    className="chat-text-input"
                    placeholder="Type a message..."
                    value={inputText}
                    onChange={handleInputChange}
                    autoFocus
                  />

                  {/* Send or Mic Action Button */}
                  {inputText.trim() ? (
                    <button
                      type="submit"
                      className="action-circle-btn send-active"
                      title="Send message"
                      aria-label="Send message"
                    >
                      ➤
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="action-circle-btn mic-btn"
                      onClick={() => setIsRecording(true)}
                      title="Record voice note"
                      aria-label="Record voice note"
                    >
                      🎙️
                    </button>
                  )}
                </form>
              )}
            </div>
          </>
        ) : (
          <div className="no-chat-selected">
            <div className="empty-icon">💬</div>
            <h3>Your Private Messages</h3>
            <p>
              Select an existing conversation from the left, or visit the Dashboard to search for a user
              and start a new conversation.
            </p>
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
