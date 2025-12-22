// src/utils/auth.js

import { baseUrl } from '../config';

const USER_INFO_KEY = 'user_info';

// Prevent duplicate refresh calls and reduce frequency
let refreshInFlight = null; // Promise for ongoing refresh
let lastRefreshTs = 0; // ms timestamp
const MIN_REFRESH_INTERVAL_MS = 60 * 1000*100; // don't refresh more than once per minute

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

// Utility: refresh access token
export async function refreshAccessToken() {
  const now = Date.now();
  // Throttle: if we refreshed very recently, reuse the last token
  if (now - lastRefreshTs < MIN_REFRESH_INTERVAL_MS && refreshInFlight === null) {
    const info = getUserInfo();
    return info?.access_token || null;
  }

  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  // Deduplicate concurrent refreshes
  if (refreshInFlight) {
    try {
      return await refreshInFlight;
    } catch (e) {
      return null;
    }
  }

  // Use a simple request to avoid CORS preflight (OPTIONS):
  // - method: POST
  // - Content-Type: application/x-www-form-urlencoded
  // - no custom headers
  const body = new URLSearchParams({ refresh_token: refreshToken });

  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${baseUrl}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
        credentials: 'include', // if your server relies on cookies; harmless otherwise
      });
      const data = await res.json();
      if (data.success && data.access_token) {
        const userInfo = getUserInfo() || {};
        userInfo.access_token = data.access_token;
        saveUserInfo(userInfo);
        lastRefreshTs = Date.now();
        return data.access_token;
      }
      return null;
    } catch (e) {
      return null;
    } finally {
      // Allow new refresh after completion
      refreshInFlight = null;
    }
  })();

  try {
    return await refreshInFlight;
  } catch (e) {
    return null;
  }
}

// Utility: get token, auto-refresh if expired
export async function getToken(forceLoginCallback) {
  const info = getUserInfo();
  let token = info?.access_token || '';
  if (!token) return '';
  const payload = parseJwt(token);
  if (!payload || !payload.exp) return token;
  const now = Math.floor(Date.now() / 1000);
  // If token expires in < 2 min, refresh
  if (payload.exp - now < 120) {
    const newToken = await refreshAccessToken();
    if (newToken) return newToken;
    if (forceLoginCallback) forceLoginCallback();
    return '';
  }
  return token;
}

// Event: auto-refresh access token before expiry
export function setupAccessTokenAutoRefresh() {
  const info = getUserInfo();
  if (!info?.access_token) return;
  const payload = parseJwt(info.access_token);
  if (!payload?.exp) return;
  const now = Math.floor(Date.now() / 1000);
  const msUntilRefresh = Math.max((payload.exp - now - 60) * 1000, 10000); // 1 min before expiry
  setTimeout(async () => {
    await refreshAccessToken();
    setupAccessTokenAutoRefresh(); // Schedule next refresh
  }, msUntilRefresh);
}

// On page load, if refresh_token is valid and access_token is missing/expired, refresh it
export async function refreshAccessTokenIfNeeded() {
  const info = getUserInfo();
  if (!info) return;
  const accessToken = info.access_token;
  const refreshToken = info.refresh_token;
  let expired = false;
  if (accessToken) {
    const payload = parseJwt(accessToken);
    if (!payload || !payload.exp || Math.floor(Date.now() / 1000) > payload.exp) expired = true;
  } else {
    expired = true;
  }
  if (refreshToken && expired) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      info.access_token = newToken;
      saveUserInfo(info);
    }
  }
}
