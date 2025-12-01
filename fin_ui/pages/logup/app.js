function navigateTo(path) {
    window.location.href = path;
}

const logupForm = document.getElementById('logupForm');
if (logupForm) {
    logupForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const form = e.target;
        const data = {
            username: form.username.value,
            email: form.email.value,
            password: form.password.value,
            phone: form.phone.value
        };
        try {
            const res = await fetch(`${window.BASE_URL}/user/register`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const result = await res.json();
            if (!res.ok) {
                let msg = result.error || result.message || 'Registration failed. Please check your details.';
                document.getElementById('logupResponse').textContent = msg;
                console.error('Registration error:', msg);
                return;
            }
            document.getElementById('logupResponse').textContent = JSON.stringify(result, null, 2);
            if(result.success) {
                // Redirect to login page on successful registration
                navigateTo('/pages/login/index.html');
            } else {
                let msg = result.error || result.message || 'Registration failed.';
                document.getElementById('logupResponse').textContent = msg;
                console.error('Registration error:', msg);
            }
        } catch (err) {
            document.getElementById('logupResponse').textContent = 'Unexpected error occurred. Please try again.';
            console.error('Unexpected registration error:', err);
        }
    });
}
