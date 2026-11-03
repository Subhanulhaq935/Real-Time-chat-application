import apiClient from './client'

export const createOrGetChat = async (participantUserId) => {
  const response = await apiClient.post('/chats', {
    participant_user_id: participantUserId,
  })
  return response.data
}

export const getChatsList = async () => {
  const response = await apiClient.get('/chats')
  return response.data
}

export const getChatMessages = async (conversationId, limit = 50, offset = 0) => {
  const response = await apiClient.get(`/chats/${conversationId}/messages`, {
    params: { limit, offset },
  })
  return response.data
}

export const sendMessageRest = async (conversationId, content) => {
  const response = await apiClient.post(`/chats/${conversationId}/messages`, {
    content,
  })
  return response.data
}

export const markChatAsRead = async (conversationId) => {
  const response = await apiClient.post(`/chats/${conversationId}/read`)
  return response.data
}

