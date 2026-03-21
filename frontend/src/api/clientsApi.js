import api from './apiClient';

export const getClients = () => api.get('/clients');
export const updateClientInfo = (clientId, data) => api.put(`/clients/${clientId}`, data);
export const acceptClientService = (clientId) => api.put(`/clients/${clientId}/accept-service`);
export const finishClientService = (clientId) => api.put(`/clients/${clientId}/finish-service`);
