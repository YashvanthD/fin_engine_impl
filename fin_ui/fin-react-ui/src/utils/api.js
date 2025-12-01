// src/utils/api.js
import { getToken } from './auth';
import { baseUrl } from '../config';

export async function apiFetch(endpoint, options = {}, forceLoginCallback) {
  const token = await getToken(forceLoginCallback);
  const headers = {
    ...(options.headers || {}),
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const url = `${baseUrl}${endpoint}`;
  console.log('[API Debug] Fetching:', url, 'Options:', options);
  return fetch(url, { ...options, headers });
}
