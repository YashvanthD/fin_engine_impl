// Roles Dropdown Component JS
async function fetchRoles() {
    const dropdown = document.getElementById('roleDropdown');
    dropdown.innerHTML = '<option>Loading...</option>';
    try {
        const res = await fetch('/api/roles');
        const roles = await res.json();
        dropdown.innerHTML = '';
        roles.forEach(role => {
            const opt = document.createElement('option');
            opt.value = role;
            opt.textContent = role.charAt(0).toUpperCase() + role.slice(1);
            dropdown.appendChild(opt);
        });
    } catch {
        dropdown.innerHTML = '<option>Error loading roles</option>';
    }
}
window.onload = fetchRoles;
<!-- Roles Dropdown Component HTML -->
<div class="roles-component">
    <h2>Select Role</h2>
    <select id="roleDropdown"></select>
</div>

