// User Dropdown Component JS
async function fetchUsers() {
    const dropdown = document.getElementById('userDropdown');
    dropdown.innerHTML = '<option>Loading...</option>';
    try {
        const res = await fetch('/api/users');
        const users = await res.json();
        dropdown.innerHTML = '';
        users.forEach(user => {
            const opt = document.createElement('option');
            opt.value = user.key || user;
            opt.textContent = user.name || user;
            dropdown.appendChild(opt);
        });
    } catch {
        dropdown.innerHTML = '<option>Error loading users</option>';
    }
}
window.onload = fetchUsers;
<!-- User Dropdown Component HTML -->
<div class="user-dropdown-component">
    <h2>Select User</h2>
    <select id="userDropdown"></select>
</div>

