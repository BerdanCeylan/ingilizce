/**
 * UI Helper Functions
 * Common UI utilities and helpers
 */

/**
 * Show error message
 */
export function showError(message) {
    const errorEl = document.getElementById('loginError');
    const successEl = document.getElementById('loginSuccess');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = message ? 'block' : 'none';
    }
    if (successEl) {
        successEl.style.display = 'none';
    }
}

/**
 * Show success message
 */
export function showSuccess(message) {
    const errorEl = document.getElementById('loginError');
    const successEl = document.getElementById('loginSuccess');
    if (successEl) {
        successEl.textContent = message;
        successEl.style.display = 'block';
    }
    if (errorEl) {
        errorEl.style.display = 'none';
    }
    // Auto-hide after 3 seconds
    setTimeout(() => {
        if (successEl) successEl.style.display = 'none';
    }, 3000);
}

/**
 * Set button loading state
 */
export function setButtonLoading(buttonId, loading) {
    const btn = document.getElementById(buttonId);
    if (btn) {
        if (loading) {
            btn.classList.add('loading');
            btn.disabled = true;
        } else {
            btn.classList.remove('loading');
            btn.disabled = false;
        }
    }
}

/**
 * Show app section (hide login)
 */
export function showAppSection() {
    const loginSection = document.getElementById('loginSection');
    const appSection = document.getElementById('appSection');
    if (loginSection) loginSection.classList.remove('active');
    if (appSection) {
        appSection.classList.add('active');
        appSection.style.display = 'block';
    }
}

/**
 * Show login section (hide app)
 */
export function showLoginSection() {
    const appSection = document.getElementById('appSection');
    const loginSection = document.getElementById('loginSection');
    if (appSection) appSection.classList.remove('active');
    if (loginSection) {
        loginSection.classList.add('active');
        loginSection.style.display = 'block';
    }
}

/**
 * Switch between tabs
 */
export function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.style.display = 'none';
    });
    
    // Remove active class from all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const tabElement = document.getElementById(tabName + 'Tab');
    if (tabElement) {
        tabElement.style.display = 'block';
    }
    
    // Add active class to selected button
    const tabBtn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
    if (tabBtn) {
        tabBtn.classList.add('active');
    }
}
