/**
 * Main Application Entry Point (Modular Version)
 * Imports and initializes all modules
 */
import { state } from './modules/state.js';
import { showAppSection, switchTab } from './modules/ui.js';
import { loginUser, registerUser, handleGoogleCredentialResponse, logout } from './modules/auth.js';

// Initialize state
state.init();

// Make state available globally for backward compatibility
window.currentUser = state.currentUser;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('App initialized (modular)');
    
    // Setup event listeners
    setupEventListeners();
    
    // Initialize socket (if exists)
    if (window.initializeSocket) {
        window.initializeSocket();
    }
    
    // Check for saved session
    if (state.currentUser) {
        showAppSection();
        switchTab('rooms');
        if (window.loadStats) window.loadStats();
    }
});

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // Login
    document.getElementById('loginBtn')?.addEventListener('click', loginUser);
    document.getElementById('registerBtn')?.addEventListener('click', registerUser);
    
    // Tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            switchTab(this.dataset.tab);
        });
    });
    
    // Logout
    document.getElementById('logoutBtn')?.addEventListener('click', logout);
    
    // Other event listeners will be set up by their respective modules
    // This is a minimal setup - more will be added as modules are created
}

// Export for global access
window.state = state;
window.switchTab = switchTab;
