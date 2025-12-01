// src/utils/auth.js

import { baseUrl } from '../config';

const USER_INFO_KEY = 'user_info';

export function saveUserInfo(userInfo) {
  localStorage.setItem(USER_INFO_KEY, JSON.stringify(userInfo));
  console.log('[Auth Debug] User info saved:', userInfo);
}

export function getUserInfo() {
  const data = localStorage.getItem(USER_INFO_KEY);
  if (!data) return null;
  try {
    return JSON.parse(data);
  } catch (e) {
    console.log('[Auth Debug] Failed to parse user info:', e);
    return null;
  }
}

export function getAccessToken() {
  const info = getUserInfo();
  return info?.access_token || '';
}

export function getRefreshToken() {
  const info = getUserInfo();
  return info?.refresh_token || '';
}

export function removeUserInfo() {
  localStorage.removeItem(USER_INFO_KEY);
  console.log('[Auth Debug] User info removed');
}

export function parseJwt(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
      return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    return JSON.parse(jsonPayload);
  } catch (e) {
    console.log('[Auth Debug] Failed to parse JWT:', e);
    return null;
  }
}

export function isTokenExpired(token) {
  const payload = parseJwt(token);
  if (!payload || !payload.exp) return true;
  return Date.now() / 1000 > payload.exp;
}

export async function getToken(forceLoginCallback) {
  const info = getUserInfo();
  if (!info) {
    console.log('[Auth Debug] No user info, forcing login');
    if (forceLoginCallback) forceLoginCallback();
    return '';
  }
  const { access_token, refresh_token } = info;
  if (!access_token || isTokenExpired(access_token)) {
    console.log('[Auth Debug] Access token expired, trying refresh token');
    if (refresh_token && !isTokenExpired(refresh_token)) {
      try {
        // Replace with your actual refresh endpoint and payload
        const res = await fetch(`${baseUrl}/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token })
        });
        const data = await res.json();
        if (res.ok && data.access_token) {
          const newInfo = { ...info, access_token: data.access_token };
          saveUserInfo(newInfo);
          console.log('[Auth Debug] Refreshed access token');
          return data.access_token;
        } else {
          console.log('[Auth Debug] Refresh token failed, forcing login');
          removeUserInfo();
          if (forceLoginCallback) forceLoginCallback();
          return '';
        }
      } catch (err) {
        console.log('[Auth Debug] Network error during token refresh', err);
        removeUserInfo();
        if (forceLoginCallback) forceLoginCallback();
        return '';
      }
    } else {
      console.log('[Auth Debug] Both tokens expired, forcing login');
      removeUserInfo();
      if (forceLoginCallback) forceLoginCallback();
      return '';
    }
  }
  return access_token;
}
