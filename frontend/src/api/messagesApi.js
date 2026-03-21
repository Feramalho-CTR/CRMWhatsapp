import api from './apiClient';

export const getConversations = () => api.get('/conversations');
export const getClientMessages = (clientId) => api.get(`/clients/${clientId}/messages`);
export const sendWhatsappMessage = (data) => api.post('/whatsapp/send', data);
