import api from './apiClient';

export const loginWithToken = () => api.get('/auth/me');
export const updateProfile = (data) => api.put('/profile/update', data);
export const changePassword = (data) => api.put('/profile/change-password', data);
