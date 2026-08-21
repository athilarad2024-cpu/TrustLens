// frontend/src/services/api.js
// Central API service — all backend calls go through here.
// Configure VITE_API_BASE_URL in frontend/.env.local for custom backend URL.

import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000,  // 2 min — video analysis can be slow
});

// ── Response normalisation ────────────────────────────────────────────────────

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err?.response?.data?.detail || err?.response?.data;
    const message =
      (typeof detail === 'object' && detail?.message) ||
      (typeof detail === 'string' && detail) ||
      err?.message ||
      'An unexpected error occurred.';
    return Promise.reject({ message, status: err?.response?.status });
  }
);

// ── Public API ────────────────────────────────────────────────────────────────

export const analyzeImage = (file, onProgress) => {
  const form = new FormData();
  form.append('file', file);
  return client.post('/analyze/image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress,
  }).then(r => r.data);
};

export const analyzeVideo = (file, onProgress) => {
  const form = new FormData();
  form.append('file', file);
  return client.post('/analyze/video', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress,
  }).then(r => r.data);
};

export const analyzeUrl = (url) =>
  client.post('/analyze/url', { url }).then(r => r.data);

export const getAnalysis = (id) =>
  client.get(`/analysis/${id}`).then(r => r.data);

export const getHistory = (params = {}) =>
  client.get('/history', { params }).then(r => r.data);

export const getHealth = () =>
  client.get('/health').then(r => r.data);

export const loginUser = (email, password) =>
  client.post('/auth/login', { email, password }).then(r => r.data);

export const registerUser = (name, email, password, confirm_password) =>
  client.post('/auth/register', { name, email, password, confirm_password }).then(r => r.data);

export const forgotPassword = (email) =>
  client.post('/auth/forgot-password', { email }).then(r => r.data);

export const resetPassword = (token, new_password, confirm_password) =>
  client.post('/auth/reset-password', { token, new_password, confirm_password }).then(r => r.data);
