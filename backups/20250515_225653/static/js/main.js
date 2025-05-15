/**
 * GHL API Clio Integration
 * Main JavaScript file
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });
    
    // Function to format JSON for display
    window.formatJSON = function(json) {
        if (typeof json === 'string') {
            try {
                json = JSON.parse(json);
            } catch (e) {
                return json;
            }
        }
        return JSON.stringify(json, null, 2);
    };

    // Copy to clipboard functionality
    const clipboardButtons = document.querySelectorAll('.copy-btn');
    if (clipboardButtons) {
        clipboardButtons.forEach(button => {
            button.addEventListener('click', function() {
                const textToCopy = this.getAttribute('data-clipboard-text');
                navigator.clipboard.writeText(textToCopy).then(() => {
                    // Show success feedback
                    const originalHTML = this.innerHTML;
                    this.innerHTML = '<i class="bi bi-check"></i>';
                    setTimeout(() => {
                        this.innerHTML = originalHTML;
                    }, 1500);
                }).catch(err => {
                    console.error('Could not copy text: ', err);
                });
            });
        });
    }

    // Date formatting
    const dateElements = document.querySelectorAll('.format-date');
    if (dateElements) {
        dateElements.forEach(element => {
            const dateString = element.textContent;
            const date = new Date(dateString);
            if (!isNaN(date)) {
                element.textContent = date.toLocaleString();
            }
        });
    }

    // Auto-hiding alerts
    const autoHideAlerts = document.querySelectorAll('.alert-auto-hide');
    if (autoHideAlerts) {
        autoHideAlerts.forEach(alert => {
            setTimeout(() => {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }, 5000); // Hide after 5 seconds
        });
    }
    
    // Configure tab persistence
    const settingsTabs = document.getElementById('settings-tabs');
    if (settingsTabs) {
        // Store active tab in local storage
        const activeTabId = localStorage.getItem('activeSettingsTab');
        if (activeTabId) {
            const tabToActivate = document.querySelector(`#settings-tabs button[data-bs-target="${activeTabId}"]`);
            if (tabToActivate) {
                const tab = new bootstrap.Tab(tabToActivate);
                tab.show();
            }
        }
        
        // Set active tab when clicked
        const tabs = settingsTabs.querySelectorAll('button[data-bs-toggle="tab"]');
        tabs.forEach(tab => {
            tab.addEventListener('shown.bs.tab', function(event) {
                localStorage.setItem('activeSettingsTab', event.target.getAttribute('data-bs-target'));
            });
        });
    }
    
    // Form validation for required fields
    const forms = document.querySelectorAll('.needs-validation');
    if (forms) {
        Array.from(forms).forEach(form => {
            form.addEventListener('submit', event => {
                if (!form.checkValidity()) {
                    event.preventDefault();
                    event.stopPropagation();
                }
                form.classList.add('was-validated');
            }, false);
        });
    }
    
    // Toggle password visibility
    const togglePasswordButtons = document.querySelectorAll('.toggle-password');
    if (togglePasswordButtons) {
        togglePasswordButtons.forEach(button => {
            button.addEventListener('click', function() {
                const input = document.querySelector(this.getAttribute('data-target'));
                if (input.type === 'password') {
                    input.type = 'text';
                    this.innerHTML = '<i class="bi bi-eye-slash"></i>';
                } else {
                    input.type = 'password';
                    this.innerHTML = '<i class="bi bi-eye"></i>';
                }
            });
        });
    }
});

// Error handling for fetch requests
function handleFetchErrors(response) {
    if (!response.ok) {
        throw Error(response.statusText);
    }
    return response;
}

// Helper function to create confirmation dialogs
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Format byte sizes to human-readable format
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Helper function to debounce function calls
function debounce(func, wait, immediate) {
    let timeout;
    return function() {
        const context = this, args = arguments;
        const later = function() {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
}

// Helper function to throttle function calls
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}
