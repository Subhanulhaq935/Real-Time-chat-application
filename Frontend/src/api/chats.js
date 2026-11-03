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

export const getChatMessages = async (conversationId, limit = 100, offset = 0) => {
  const response = await apiClient.get(`/chats/${conversationId}/messages`, {
    params: { limit, offset },
  })
  return response.data
}

export const sendMessageRest = async (conversationId, content, message_type = 'text', media_url = null, media_duration = null) => {
  const response = await apiClient.post(`/chats/${conversationId}/messages`, {
    content,
    message_type,
    media_url,
    media_duration,
  })
  return response.data
}

export const editMessageRest = async (conversationId, messageId, content) => {
  const response = await apiClient.patch(`/chats/${conversationId}/messages/${messageId}`, {
    content,
  })
  return response.data
}

export const deleteMessageRest = async (conversationId, messageId, deleteType = 'everyone') => {
  const response = await apiClient.delete(`/chats/${conversationId}/messages/${messageId}`, {
    data: { delete_type: deleteType },
  })
  return response.data
}

export const toggleReactionRest = async (conversationId, messageId, emoji) => {
  const response = await apiClient.post(`/chats/${conversationId}/messages/${messageId}/reactions`, {
    emoji,
  })
  return response.data
}

export const markChatAsRead = async (conversationId) => {
  const response = await apiClient.post(`/chats/${conversationId}/read`)
  return response.data
}
