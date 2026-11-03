import apiClient from './client'

export const signup = async (data) => {
  const response = await apiClient.post('/auth/signup', data)
  return response.data
}

export const verifyOtp = async (data) => {
  const response = await apiClient.post('/auth/verify-otp', data)
  return response.data
}

export const resendOtp = async (data) => {
  const response = await apiClient.post('/auth/resend-otp', data)
  return response.data
}

export const loginUser = async (data) => {
  const response = await apiClient.post('/auth/login', data)
  return response.data
}

export const getMe = async () => {
  const response = await apiClient.get('/auth/me')
  return response.data
}

export const logoutUser = async () => {
  const response = await apiClient.post('/auth/logout')
  return response.data
}


