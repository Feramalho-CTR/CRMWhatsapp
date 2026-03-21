import api from './apiClient';

export const getAdminUsers = () => api.get('/admin/users');
export const createAdminUser = (data) => api.post('/admin/users', data);
export const updateAdminUser = (userId, data) => api.put(`/admin/users/${userId}`, data);
export const deleteAdminUser = (userId) => api.delete(`/admin/users/${userId}`);
export const resetUserPassword = (userId, password) => api.post(`/admin/users/${userId}/reset-password`, { password });

export const getWhatsappConfig = () => api.get('/admin/whatsapp-config');
export const updateWhatsappConfig = (config) => api.put('/admin/whatsapp-config', config);
export const testWhatsapp = () => api.post('/admin/test-whatsapp');
export const obtainWhatsappAppToken = () => api.post('/admin/whatsapp-obtain-app-token');

export const getAgentsPerformance = () => api.get('/admin/agents-performance');
export const getServiceMetrics = () => api.get('/admin/service-metrics');
export const adminAssignClient = (clientId, agentId) => api.post(`/admin/assign-client/${clientId}`, { agent_id: agentId });
