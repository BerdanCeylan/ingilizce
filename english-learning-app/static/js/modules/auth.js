/**
 * Authentication Module
 * Handles user login, registration, and authentication
 */
import { state } from './state.js';
import { showError, showSuccess, setButtonLoading, showAppSection, switchTab } from './ui.js';
import { apiPost } from './api.js';

/**
 * Login user
 */
export async function loginUser() {
    const username = document.getElementById('username')?.value.trim();
    const password = document.getElementById('password')?.value;
    const rememberMe = document.getElementById('rememberMe')?.checked;
    
    showError('');
    
    if (!username || !password) {
        showError('Lütfen kullanıcı adı ve şifre girin');
        return;
    }

    setButtonLoading('loginBtn', true);

    try {
        const data = await apiPost('/api/auth/login', { username, password });
        
        setButtonLoading('loginBtn', false);
        
        if (data.success) {
            state.currentUser = data;
            state.saveUser(rememberMe);
            showSuccess('Giriş başarılı! Yönlendiriliyorsunuz...');
            
            setTimeout(() => {
                showAppSection();
                switchTab('rooms');
                if (window.loadStats) window.loadStats();
                if (window.executePendingAction) window.executePendingAction();
            }, 500);
        } else {
            showError(data.error || 'Giriş yapılamadı. Lütfen bilgilerinizi kontrol edin.');
        }
    } catch (err) {
        setButtonLoading('loginBtn', false);
        console.error('Login error:', err);
        showError('Bağlantı hatası. Lütfen tekrar deneyin.');
    }
}

/**
 * Register user
 */
export async function registerUser() {
    const username = document.getElementById('username')?.value.trim();
    const password = document.getElementById('password')?.value;
    
    showError('');
    
    if (!username || !password) {
        showError('Lütfen kullanıcı adı ve şifre girin');
        return;
    }

    if (password.length < 6) {
        showError('Şifre en az 6 karakter olmalıdır');
        return;
    }

    setButtonLoading('registerBtn', true);

    try {
        const data = await apiPost('/api/auth/register', { username, password });
        
        setButtonLoading('registerBtn', false);
        
        if (data.success) {
            showSuccess('✅ ' + (data.message || 'Kayıt başarılı! Giriş yapılıyor...'));
            setTimeout(() => {
                loginUser();
            }, 1000);
        } else {
            showError('❌ ' + (data.error || 'Kayıt yapılamadı'));
        }
    } catch (err) {
        setButtonLoading('registerBtn', false);
        console.error('Register error:', err);
        showError('Kayıt sırasında bir hata oluştu. Lütfen tekrar deneyin.');
    }
}

/**
 * Handle Google Sign-In
 */
export async function handleGoogleCredentialResponse(response) {
    const errorEl = document.getElementById('loginError');
    const successEl = document.getElementById('loginSuccess');
    
    if (successEl) {
        successEl.textContent = 'Google ile giriş yapılıyor...';
        successEl.style.display = 'block';
    }
    if (errorEl) {
        errorEl.style.display = 'none';
    }

    try {
        const data = await apiPost('/api/auth/google', { token: response.credential });
        
        if (data.success) {
            state.currentUser = data;
            
            const rememberMe = document.getElementById('rememberMe')?.checked;
            state.saveUser(rememberMe);
            
            if (successEl) {
                successEl.textContent = 'Google ile giriş başarılı! Yönlendiriliyorsunuz...';
            }
            
            setTimeout(() => {
                showAppSection();
                switchTab('rooms');
                if (window.loadStats) window.loadStats();
                if (window.executePendingAction) window.executePendingAction();
            }, 500);
        } else {
            showError('❌ Google girişi başarısız: ' + (data.error || 'Bilinmeyen hata'));
        }
    } catch (err) {
        console.error('Google auth error:', err);
        showError('Google ile giriş yapılırken bir hata oluştu. Lütfen tekrar deneyin.');
    }
}

/**
 * Logout user
 */
export function logout() {
    window.currentUser = null;
    
    if (state.roomsInterval) {
        clearInterval(state.roomsInterval);
        state.roomsInterval = null;
    }
    
    state.clearUser();
    state.currentRoom = null;
    
    if (state.socket) {
        state.socket.disconnect();
        state.socket = null;
    }
    
    const loginSection = document.getElementById('loginSection');
    if (loginSection) {
        loginSection.classList.add('active');
        loginSection.style.display = 'block';
    }
    
    const appSection = document.getElementById('appSection');
    if (appSection) {
        appSection.classList.remove('active');
        appSection.style.display = 'none';
    }
    
    // Clear form
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    if (usernameInput) usernameInput.value = '';
    if (passwordInput) passwordInput.value = '';
}

// Export for global access (for inline scripts)
window.loginUser = loginUser;
window.registerUser = registerUser;
window.handleGoogleCredentialResponse = handleGoogleCredentialResponse;
window.logout = logout;
