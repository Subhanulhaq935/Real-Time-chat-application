import React, { createContext, useContext, useState, useEffect } from 'react'
import { getMe, loginUser, logoutUser } from '../api/auth'

const AuthContext = createContext(null)

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // Verify persistent session on mount
  useEffect(() => {
    const checkSession = async () => {
      try {
        const userData = await getMe()
        setUser(userData)
      } catch (err) {
        // No active session or token expired
        localStorage.removeItem('access_token')
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
    setUser(data.user)
    return data
  }

  const logout = async () => {
    try {
      await logoutUser()
    } catch (err) {
      console.warn('Logout API notice:', err)
    } finally {
      localStorage.removeItem('access_token')
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

