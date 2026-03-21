import api from './apiClient';

export const getMyStatus = () => api.get('/agent/my-status');
export const updateAgentStatus = (status) => api.put('/agent/status', { status });
