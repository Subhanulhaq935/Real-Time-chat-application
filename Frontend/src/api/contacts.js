import apiClient from './client'

export const searchUserByEmail = async (email) => {
  const response = await apiClient.get('/users/search', {
    params: { email: email.trim().toLowerCase() },
  })
  return response.data
}

export const getContactsList = async () => {
  const response = await apiClient.get('/contacts')
  return response.data
}

export const saveContact = async (contactUserId, customName) => {
  const response = await apiClient.post('/contacts', {
    contact_user_id: contactUserId,
    custom_name: customName.trim(),
  })
  return response.data
}

export const updateContactCustomName = async (contactUserId, customName) => {
  const response = await apiClient.patch(`/contacts/${contactUserId}`, {
    custom_name: customName.trim(),
  })
  return response.data
}

export const resetContactCustomName = async (contactUserId) => {
  const response = await apiClient.delete(`/contacts/${contactUserId}`)
  return response.data
}

