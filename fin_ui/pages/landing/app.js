// Dynamically show/hide landing actions based on login status
window.onload = function() {
    const userJson = sessionStorage.getItem('user');
    const actionsDiv = document.querySelector('.landing-actions');
    if (userJson && actionsDiv) {
        // User is logged in, show only Home and Logout
        actionsDiv.innerHTML = `
            <a href="/pages/home/index.html" class="landing-btn">Home</a>
            <button id="logoutBtn" class="landing-btn">Logout</button>
        `;
        document.getElementById('logoutBtn').onclick = function() {
            sessionStorage.clear();
            window.location.href = '/pages/login/index.html';
        };
    }
}

