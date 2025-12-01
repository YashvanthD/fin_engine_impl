// SPA Navigation Helper
function navigateTo(path) {
    window.location.href = path;
}

const loginForm = document.getElementById('loginForm');
if (loginForm) {
    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const form = e.target;
        const data = {
            username: form.username.value,
            password: form.password.value
        };
        try {
            const res = await fetch(`${window.BASE_URL}/auth/login`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const result = await res.json();
            if (!res.ok) {
                let msg = result.error || result.message || 'Login failed. Please check your credentials.';
                document.getElementById('loginResponse').textContent = msg;
                console.error('Login error:', msg);
                return;
            }
            document.getElementById('loginResponse').textContent = JSON.stringify(result, null, 2);
            if(result.success) {
                // Store access_token and refresh_token in sessionStorage
                if (result.access_token) {
                    sessionStorage.setItem('access_token', result.access_token);
                }
                if (result.refresh_token) {
                    sessionStorage.setItem('refresh_token', result.refresh_token);
                }
                if (result.token) {
                    sessionStorage.setItem('refresh_token', result.token);
                }
                if (result.user) {
                    sessionStorage.setItem('user', JSON.stringify(result.user));
                }
                // Optionally store other details
                if (result.account_key) {
                    sessionStorage.setItem('account_key', result.account_key);
                }
                if (result.user_key) {
                    sessionStorage.setItem('user_key', result.user_key);
                }
                // Redirect to home page on successful login
                navigateTo('../home/index.html');
            } else {
                let msg = result.error || result.message || 'Login failed.';
                document.getElementById('loginResponse').textContent = msg;
                console.error('Login error:', msg);
            }
        } catch (err) {
            document.getElementById('loginResponse').textContent = 'Unexpected error occurred. Please try again.';
            console.error('Unexpected login error:', err);
        }
    });
}
