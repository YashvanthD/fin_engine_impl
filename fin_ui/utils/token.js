// General token utility for frontend
window.getAccessToken = function() {
    return sessionStorage.getItem('access_token');
};
window.getRefreshToken = function() {
    return sessionStorage.getItem('refresh_token');
};
window.setAccessToken = function(token) {
    sessionStorage.setItem('access_token', token);
};
window.setRefreshToken = function(token) {
    sessionStorage.setItem('refresh_token', token);
};
window.refreshAccessToken = async function(baseUrl) {
    const refreshToken = window.getRefreshToken();
    if (!refreshToken) return null;
    try {
        const res = await fetch(`${baseUrl}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        const result = await res.json();
        if (res.ok && result.access_token) {
            window.setAccessToken(result.access_token);
            return result.access_token;
        }
    } catch (err) {
        console.error('Failed to refresh access token:', err);
    }
    return null;
};
window.authFetch = async function(url, options = {}, baseUrl, retry = true) {
    let accessToken = window.getAccessToken();
    options.headers = options.headers || {};
    if (accessToken) {
        options.headers['Authorization'] = `Bearer ${accessToken}`;
    }
    let res = await fetch(url, options);
    if (res.status === 401 && retry) {
        accessToken = await window.refreshAccessToken(baseUrl);
        if (accessToken) {
            options.headers['Authorization'] = `Bearer ${accessToken}`;
            res = await fetch(url, options);
        }
    }
    return res;
};
