// Home Page JS
// You can add logic for authentication, fetching user info, etc. here

function navigateTo(path) {
    window.location.href = path;
}

// Use global token functions, no import needed
function requireTokenOrRedirect() {
    const accessToken = window.getAccessToken();
    if (!accessToken) {
        alert('Session expired or missing. Please login again.');
        window.location.href = '../login/index.html';
        return false;
    }
    return true;
}

// Show user info if logged in
window.onload = function() {
    try {
        const userJson = sessionStorage.getItem('user');
        if (!requireTokenOrRedirect()) return;
        const accessToken = window.getAccessToken();
        const homeContainer = document.querySelector('.home-container');
        if (userJson && homeContainer) {
            const user = JSON.parse(userJson);
            const userInfoDiv = document.createElement('div');
            userInfoDiv.className = 'user-info';
            userInfoDiv.innerHTML = `<p>Welcome, <b>${user.username || user.name || user.email}</b>!</p>
                <button id="logoutBtn" class="home-btn" style="margin-top:16px;">Logout</button>`;
            homeContainer.insertBefore(userInfoDiv, homeContainer.firstChild);
            document.getElementById('logoutBtn').onclick = function() {
                sessionStorage.clear();
                navigateTo('../login/index.html');
            };
            // Fetch tasks/notifications for summary and recent
            fetchSummaryAndNotifications(accessToken, user);
        }
    } catch (err) {
        const homeContainer = document.querySelector('.home-container');
        if (homeContainer) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-msg';
            errorDiv.textContent = 'Error loading user info.';
            homeContainer.insertBefore(errorDiv, homeContainer.firstChild);
        }
        console.error('Error loading user info:', err);
    }
    // Modal logic for create task
    const createTaskBtn = document.getElementById('createTaskBtn');
    const createTaskModal = document.getElementById('createTaskModal');
    const closeModal = document.getElementById('closeModal');
    if (createTaskBtn && createTaskModal && closeModal) {
        createTaskBtn.onclick = () => createTaskModal.style.display = 'block';
        closeModal.onclick = () => createTaskModal.style.display = 'none';
        window.onclick = function(event) {
            if (event.target === createTaskModal) createTaskModal.style.display = 'none';
        };
    }
    // Handle create task form
    const createTaskForm = document.getElementById('createTaskForm');
    if (createTaskForm) {
        createTaskForm.onsubmit = async function(e) {
            if (!requireTokenOrRedirect()) return;
            const form = e.target;
            const data = {
                title: form.title.value,
                description: form.description.value,
                end_date: form.end_date.value,
                reminder_time: form.reminder_time.value,
                assignee: form.assignee.value
            };
            try {
                const res = await window.authFetch(`${window.BASE_URL}/task/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                }, window.BASE_URL);
                const result = await res.json();
                if (!res.ok) {
                    document.getElementById('createTaskResponse').textContent = result.error || result.message || 'Task creation failed.';
                    return;
                }
                document.getElementById('createTaskResponse').textContent = 'Task created successfully!';
                createTaskModal.style.display = 'none';
                fetchSummaryAndNotifications(sessionStorage.getItem('access_token'), JSON.parse(sessionStorage.getItem('user')));
            } catch (err) {
                document.getElementById('createTaskResponse').textContent = 'Unexpected error occurred.';
            }
        };
    }
};

async function fetchSummaryAndNotifications(accessToken, user) {
    if (!requireTokenOrRedirect()) return;
    try {
        const res = await window.authFetch(`${window.BASE_URL}/task/user/${user.user_key}`, {
            method: 'GET'
        }, window.BASE_URL);
        const result = await res.json();
        if (!res.ok) {
            document.getElementById('summaryBar').textContent = result.error || result.message || 'Failed to fetch summary.';
            return;
        }
        // Summary bar
        const summary = result.summary || {};
        document.getElementById('summaryBar').innerHTML = `
            <div class="summary-item">Total: <b>${summary.total || 0}</b></div>
            <div class="summary-item">Completed: <b>${summary.completed || 0}</b></div>
            <div class="summary-item">Pending: <b>${summary.pending || 0}</b></div>
            <div class="summary-item">Overdue: <b>${summary.overdue || 0}</b></div>
            <div class="summary-item">Unread: <b>${summary.unread || 0}</b></div>
        `;
        // Notifications section
        const notifications = result.notifications || [];
        const section = document.getElementById('notificationsSection');
        if (notifications.length) {
            section.innerHTML = notifications.map(n => `
                <div class="notification-item${n.viewed ? '' : ' unread'}">
                    <div><b>${n.title}</b> - ${n.status} ${n.viewed ? '' : '<span class="badge">NEW</span>'}</div>
                    <div>${n.description}</div>
                    <div class="actions">
                        <button onclick="openNotification('${n.task_id}')">Open</button>
                        ${!n.viewed ? `<button onclick="markAsViewed('${n.task_id}')">Mark as Viewed</button>` : ''}
                        <button onclick="showReassignModal('${n.task_id}')">Reassign</button>
                    </div>
                </div>
            `).join('');
        } else {
            section.innerHTML = '<div>No notifications found.</div>';
        }
    } catch (err) {
        document.getElementById('summaryBar').textContent = 'Unexpected error occurred.';
        document.getElementById('notificationsSection').textContent = '';
    }
}

window.openNotification = function(taskId) {
    alert('Open notification for task: ' + taskId);
    // You can expand this to show task details in a modal
};
window.markAsViewed = async function(taskId) {
    if (!requireTokenOrRedirect()) return;
    const accessToken = window.getAccessToken();
    try {
        const res = await window.authFetch(`${window.BASE_URL}/task/${taskId}/viewed`, {
            method: 'POST'
        }, window.BASE_URL);
        const result = await res.json();
        if (res.ok) {
            fetchSummaryAndNotifications(accessToken, JSON.parse(sessionStorage.getItem('user')));
        }
    } catch {}
};
window.showReassignModal = function(taskId) {
    if (!requireTokenOrRedirect()) return;
    const newAssignee = prompt('Enter new assignee (username/email/phone):');
    if (newAssignee) {
        reassignTask(taskId, newAssignee);
    }
};
async function reassignTask(taskId, newAssignee) {
    if (!requireTokenOrRedirect()) return;
    const accessToken = window.getAccessToken();
    try {
        const res = await window.authFetch(`${window.BASE_URL}/task/${taskId}/reassign`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ new_assignee: newAssignee })
        }, window.BASE_URL);
        const result = await res.json();
        if (res.ok) {
            fetchSummaryAndNotifications(accessToken, JSON.parse(sessionStorage.getItem('user')));
        } else {
            alert(result.error || result.message || 'Reassign failed.');
        }
    } catch (err) {
        alert('Unexpected error occurred.');
    }
}
