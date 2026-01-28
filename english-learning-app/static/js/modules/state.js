/**
 * Global State Management
 * Centralized state for the application
 */
export const state = {
    currentUser: null,
    currentFilter: 'all',
    currentRoom: null,
    socket: null,
    isScreenSharing: false,
    peerConnection: null,
    userWordsMap: new Map(),
    roomsInterval: null,
    currentOpenPackageId: null,
    flashcardSessionId: null,
    flashcardCurrentWord: null,
    flashcardIsFlipped: false,
    
    // Initialize from storage
    init() {
        const savedUser = localStorage.getItem('currentUser') || sessionStorage.getItem('currentUser');
        if (savedUser) {
            try {
                this.currentUser = JSON.parse(savedUser);
                window.currentUser = this.currentUser; // For inline scripts
            } catch (e) {
                localStorage.removeItem('currentUser');
                sessionStorage.removeItem('currentUser');
            }
        } else {
            window.currentUser = null;
        }
    },
    
    // Save user to storage
    saveUser(rememberMe = false) {
        if (this.currentUser) {
            if (rememberMe) {
                localStorage.setItem('currentUser', JSON.stringify(this.currentUser));
                sessionStorage.removeItem('currentUser');
            } else {
                sessionStorage.setItem('currentUser', JSON.stringify(this.currentUser));
                localStorage.removeItem('currentUser');
            }
            window.currentUser = this.currentUser;
        }
    },
    
    // Clear user
    clearUser() {
        this.currentUser = null;
        window.currentUser = null;
        localStorage.removeItem('currentUser');
        sessionStorage.removeItem('currentUser');
    }
};
