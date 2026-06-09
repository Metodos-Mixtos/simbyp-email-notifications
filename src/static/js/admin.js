// Admin Interface JavaScript for SIMBYP User Management

let allUsers = [];
let currentEditUserId = null;

function isValidUuid(value) {
    return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value.trim());
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadUsers();
    setupSearchFilter();
});

// Load all users
async function loadUsers() {
    const spinner = document.getElementById('loadingSpinner');
    const tableContainer = document.getElementById('userTableContainer');
    const emptyState = document.getElementById('emptyState');
    
    spinner.style.display = 'block';
    tableContainer.style.display = 'none';
    emptyState.style.display = 'none';
    
    try {
        const response = await fetch('/api/users');
        const result = await response.json();
        
        spinner.style.display = 'none';
        
        if (!result.success) {
            showToast('Error loading users: ' + result.error, 'danger');
            return;
        }
        
        allUsers = result.data;
        renderUsers(allUsers);
        
        if (allUsers.length === 0) {
            emptyState.style.display = 'block';
        } else {
            tableContainer.style.display = 'block';
        }
        
    } catch (error) {
        spinner.style.display = 'none';
        showToast('Failed to load users: ' + error.message, 'danger');
    }
}

// Render users in table
function renderUsers(users) {
    const tbody = document.getElementById('userTableBody');
    tbody.innerHTML = '';
    
    users.forEach(user => {
        const tr = document.createElement('tr');
        
        const subscriptionBadges = user.subscriptions.map(sub => {
            const label = sub === 'weekly_alerts' ? 'Weekly Alerts' : 'Monthly Built Area';
            const color = sub === 'weekly_alerts' ? 'primary' : 'success';
            return `<span class="badge bg-${color} subscription-badge">${label}</span>`;
        }).join('');
        
        tr.innerHTML = `
            <td>${escapeHtml(user.email)}</td>
            <td>${escapeHtml(user.name || '-')}</td>
            <td>${escapeHtml(user.department || '-')}</td>
            <td>${escapeHtml(user.municipality_code || '-')}</td>
            <td>${subscriptionBadges || '<span class="text-muted">None</span>'}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="editUser('${user.id}')">Edit</button>
                <button class="btn btn-sm btn-outline-danger" onclick="confirmDeleteUser('${user.id}', '${escapeHtml(user.email)}')">Delete</button>
            </td>
        `;
        
        tbody.appendChild(tr);
    });
}

// Setup search filter
function setupSearchFilter() {
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        
        if (!query) {
            renderUsers(allUsers);
            return;
        }
        
        const filtered = allUsers.filter(user => 
            (user.email && user.email.toLowerCase().includes(query)) ||
            (user.name && user.name.toLowerCase().includes(query)) ||
            (user.department && user.department.toLowerCase().includes(query))
        );
        
        renderUsers(filtered);
    });
}

// Reset user form (for adding new user)
function resetUserForm() {
    currentEditUserId = null;
    document.getElementById('modalTitle').textContent = 'Add User';
    document.getElementById('userId').value = '';
    document.getElementById('userForm').reset();
    document.getElementById('subWeekly').checked = false;
    document.getElementById('subMonthly').checked = false;
}

// Edit user
async function editUser(userId) {
    try {
        const response = await fetch(`/api/users/${userId}`);
        const result = await response.json();
        
        if (!result.success) {
            showToast('Error loading user: ' + result.error, 'danger');
            return;
        }
        
        const user = result.data;
        currentEditUserId = userId;
        
        document.getElementById('modalTitle').textContent = 'Edit User';
        document.getElementById('userId').value = user.id;
        document.getElementById('userEmail').value = user.email;
        document.getElementById('userName').value = user.name || '';
        document.getElementById('userDepartment').value = user.department || '';
        document.getElementById('userMunicipality').value = user.municipality_code || '';
        document.getElementById('subWeekly').checked = user.subscriptions.includes('weekly_alerts');
        document.getElementById('subMonthly').checked = user.subscriptions.includes('monthly_built_area');
        
        const modal = new bootstrap.Modal(document.getElementById('userModal'));
        modal.show();
        
    } catch (error) {
        showToast('Failed to load user: ' + error.message, 'danger');
    }
}

// Save user (create or update)
async function saveUser(event) {
    event.preventDefault();
    
    const form = document.getElementById('userForm');
    
    if (!form.checkValidity()) {
        event.stopPropagation();
        form.reportValidity();
        return;
    }
    
    const email = document.getElementById('userEmail').value.trim();
    const name = document.getElementById('userName').value.trim() || null;
    const department = document.getElementById('userDepartment').value.trim() || null;
    const municipality_code = document.getElementById('userMunicipality').value.trim() || null;
    
    const subscriptions = [];
    if (document.getElementById('subWeekly').checked) {
        subscriptions.push('weekly_alerts');
    }
    if (document.getElementById('subMonthly').checked) {
        subscriptions.push('monthly_built_area');
    }
    
    const userData = {
        email,
        name,
        department,
        municipality_code,
        subscriptions
    };
    
    const isEdit = currentEditUserId !== null;
    if (isEdit && !isValidUuid(currentEditUserId)) {
        showToast('Error: Invalid user ID for update', 'danger');
        return;
    }

    const endpoint = isEdit
        ? `/api/users/${encodeURIComponent(currentEditUserId)}`
        : '/api/users';
    const method = isEdit ? 'PUT' : 'POST';
    const requestUrl = new URL(endpoint, window.location.origin).toString();
    
    const saveButton = event.currentTarget || document.getElementById('saveUserButton');
    const spinner = saveButton ? saveButton.querySelector('.loading') : null;
    if (!saveButton || !spinner) {
        showToast('Error: Save button is not available', 'danger');
        return;
    }
    spinner.classList.add('show');
    saveButton.disabled = true;
    
    try {
        const response = await fetch(requestUrl, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        });
        
        const result = await response.json();
        
        if (!result.success) {
            showToast('Error: ' + result.error, 'danger');
            return;
        }
        
        showToast(result.message, 'success');
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('userModal'));
        modal.hide();
        
        await loadUsers();
        
    } catch (error) {
        showToast('Failed to save user: ' + error.message, 'danger');
    } finally {
        spinner.classList.remove('show');
        saveButton.disabled = false;
    }
}

// Confirm delete user
function confirmDeleteUser(userId, email) {
    if (confirm(`Are you sure you want to delete user "${email}"?\n\nThis will also delete all their subscriptions and audit logs.`)) {
        deleteUser(userId);
    }
}

// Delete user
async function deleteUser(userId) {
    try {
        const response = await fetch(`/api/users/${userId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (!result.success) {
            showToast('Error: ' + result.error, 'danger');
            return;
        }
        
        showToast(result.message, 'success');
        await loadUsers();
        
    } catch (error) {
        showToast('Failed to delete user: ' + error.message, 'danger');
    }
}

// Show toast notification
function showToast(message, type = 'info') {
    const container = document.querySelector('.toast-container');
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${escapeHtml(message)}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    container.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast, { delay: 4000 });
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
