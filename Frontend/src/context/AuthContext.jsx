import React, { createContext, useContext, useState, useEffect } from 'react'
import { getMe, loginUser, logoutUser } from '../api/auth'

const AuthContext = createContext(null)

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    try {
      const token = localStorage.getItem('access_token')
      const saved = localStorage.getItem('cached_user')
      if (token && saved) {
        return JSON.parse(saved)
      }
    } catch {}
    return null
  })
  const [loading, setLoading] = useState(() => {
    const token = localStorage.getItem('access_token')
    const saved = localStorage.getItem('cached_user')
    // Don't block screen if we already have a cached user profile
    return Boolean(token && !saved)
  })

  // Verify persistent session on mount in background
  useEffect(() => {
    const checkSession = async () => {
      const token = localStorage.getItem('access_token')
      if (!token) {
        setUser(null)
        setLoading(false)
        return
      }

      try {
        const userData = await getMe()
        setUser(userData)
        try {
          localStorage.setItem('cached_user', JSON.stringify(userData))
        } catch {}
      } catch (err) {
        // No active session or token expired
        localStorage.removeItem('access_token')
        localStorage.removeItem('cached_user')
        setUser(null)
      } finally {
        setLoading(false)
      }
    }

    checkSession()
  }, [])

  const login = async (email, password) => {
    const data = await loginUser({ email, password })
    if (data.access_token) {
      localStorage.setItem('access_token', data.access_token)
    }
    if (data.user) {
      try {
        localStorage.setItem('cached_user', JSON.stringify(data.user))
      } catch {}
      setUser(data.user)
    }
    return data
  }

  const logout = async () => {
    try {
      await logoutUser()
    } catch (err) {
      console.warn('Logout API notice:', err)
    } finally {
      localStorage.removeItem('access_token')
      localStorage.removeItem('cached_user')
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

