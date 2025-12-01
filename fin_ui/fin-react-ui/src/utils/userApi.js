import { apiFetch } from './api';
import { getUserInfo, getAccessToken } from './auth';
import { getDefaultEndDate } from './date';

export async function fetchAccountUsers() {
  const userInfo = getUserInfo();
  if (!userInfo?.account_key) return [];
  const token = getAccessToken();
  const res = await apiFetch(`/user/list`, {
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const data = await res.json();
  if (res.ok && data.success && Array.isArray(data.users)) {
    return data.users;
  }
  return [];
}
