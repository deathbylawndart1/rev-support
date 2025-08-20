// Support Dashboard JavaScript functionality

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Real-time updates for dashboard
    if (window.location.pathname === '/dashboard') {
        setInterval(updateDashboardStats, 30000); // Update every 30 seconds
    }

    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // Message status updates
    const statusSelects = document.querySelectorAll('select[name="status"]');
    statusSelects.forEach(select => {
        select.addEventListener('change', function() {
            const form = this.closest('form');
            if (form) {
                form.submit();
            }
        });
    });

    // Confirmation dialogs
    const deleteButtons = document.querySelectorAll('[data-confirm]');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(event) {
            const message = this.getAttribute('data-confirm') || 'Are you sure?';
            if (!confirm(message)) {
                event.preventDefault();
            }
        });
    });

    // Auto-refresh message list
    if (window.location.pathname === '/messages') {
        setInterval(() => {
            checkForNewMessages();
        }, 15000); // Check every 15 seconds
    }

    // Notification sound for new messages
    // Create audio object with error handling for missing notification sound
    const audio = new Audio('/static/sounds/notification.mp3');
    audio.addEventListener('error', function() {
        console.log('Notification sound not available, using silent notification');
    });
    
    // WebSocket connection for real-time updates (if available)
    if (typeof io !== 'undefined') {
        const socket = io();
        
        socket.on('new_message', function(data) {
            showNotification('New support message received!', 'info');
            if (window.location.pathname === '/dashboard') {
                updateDashboardStats();
            }
        });
        
        socket.on('message_updated', function(data) {
            if (window.location.pathname.includes('/message/')) {
                location.reload();
            }
        });
    }
});

// Function to update dashboard statistics
function updateDashboardStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            document.querySelector('.total-messages').textContent = data.total;
            document.querySelector('.open-messages').textContent = data.open;
            document.querySelector('.in-progress-messages').textContent = data.in_progress;
            document.querySelector('.resolved-messages').textContent = data.resolved;
        })
        .catch(error => console.error('Error updating stats:', error));
}

// Function to check for new messages
function checkForNewMessages() {
    const lastUpdate = localStorage.getItem('lastMessageCheck') || '0';
    
    fetch(`/api/messages/check?since=${lastUpdate}`)
        .then(response => response.json())
        .then(data => {
            if (data.new_messages > 0) {
                showNotification(`${data.new_messages} new message(s) received!`, 'info');
                localStorage.setItem('lastMessageCheck', Date.now().toString());
            }
        })
        .catch(error => console.error('Error checking for new messages:', error));
}

// Function to show notifications
function showNotification(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Function to format timestamps
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) { // Less than 1 minute
        return 'Just now';
    } else if (diff < 3600000) { // Less than 1 hour
        return `${Math.floor(diff / 60000)} minutes ago`;
    } else if (diff < 86400000) { // Less than 1 day
        return `${Math.floor(diff / 3600000)} hours ago`;
    } else {
        return date.toLocaleDateString();
    }
}

// Function to copy text to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!', 'success');
    }).catch(err => {
        console.error('Failed to copy text: ', err);
        showNotification('Failed to copy text', 'danger');
    });
}

// Function to toggle user status
function toggleUserStatus(userId) {
    fetch(`/api/users/${userId}/toggle-status`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            showNotification('Failed to update user status', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error updating user status', 'danger');
    });
}

// Function to assign message to current user
function assignToMe(messageId) {
    fetch(`/api/messages/${messageId}/assign`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            showNotification('Failed to assign message', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error assigning message', 'danger');
    });
}

// Function to mark message as urgent
function markAsUrgent(messageId) {
    fetch(`/api/messages/${messageId}/priority`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ priority: 'urgent' })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            showNotification('Failed to update priority', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error updating priority', 'danger');
    });
}

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Ctrl/Cmd + R to refresh current page
    if ((event.ctrlKey || event.metaKey) && event.key === 'r') {
        event.preventDefault();
        location.reload();
    }
    
    // Ctrl/Cmd + D to go to dashboard
    if ((event.ctrlKey || event.metaKey) && event.key === 'd') {
        event.preventDefault();
        window.location.href = '/dashboard';
    }
    
    // Ctrl/Cmd + M to go to messages
    if ((event.ctrlKey || event.metaKey) && event.key === 'm') {
        event.preventDefault();
        window.location.href = '/messages';
    }
});

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Initialize popovers
document.addEventListener('DOMContentLoaded', function() {
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});
