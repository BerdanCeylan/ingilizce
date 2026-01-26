let currentUser = null;
let currentFilter = 'all';
let currentRoom = null;
let socket = null;
let isScreenSharing = false;
let peerConnection = null;
let userWordsMap = new Map(); // Kelime durumu takibi için
let roomsInterval = null;
let currentOpenPackageId = null; // Açık olan seviye paketini takip etmek için
let flashcardSessionId = null;
let flashcardCurrentWord = null;
let flashcardIsFlipped = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('App initialized');
    initializeSocket();
    setupEventListeners();

    // Check for saved session
    const savedUser = localStorage.getItem('currentUser') || sessionStorage.getItem('currentUser');
    if (savedUser) {
        try {
            currentUser = JSON.parse(savedUser);
            window.currentUser = currentUser; // Make available to inline scripts
            showAppSection();
            switchTab('rooms');
            loadStats();
        } catch (e) {
            localStorage.removeItem('currentUser');
            sessionStorage.removeItem('currentUser');
        }
    } else {
        // Initialize window.currentUser even if not logged in
        window.currentUser = null;
    }
});

// Setup all event listeners
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
    
    // Room creation
    document.getElementById('createRoomBtn')?.addEventListener('click', createNewRoom);
    
    // Screen share and leave room
    document.getElementById('screenShareBtn')?.addEventListener('click', toggleScreenShare);
    document.getElementById('shareRoomBtn')?.addEventListener('click', shareRoom);
    document.getElementById('leaveRoomBtn')?.addEventListener('click', leaveRoom);
    
    // Chat
    document.getElementById('sendChatBtn')?.addEventListener('click', sendMessage);
    document.getElementById('chatInput')?.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
    
    // Process videos
    document.getElementById('processBtn')?.addEventListener('click', processVideos);
    
    // Process video from URL
    document.getElementById('processUrlBtn')?.addEventListener('click', processVideoUrl);
    
    // Process from Dizibox
    document.getElementById('processDiziboxBtn')?.addEventListener('click', processDiziboxVideo);
    
    // Load words
    document.getElementById('loadWordsBtn')?.addEventListener('click', loadWords);
    
    // Load videos
    document.getElementById('refreshVideosBtn')?.addEventListener('click', loadVideos);
    
    // Filter buttons
    document.querySelectorAll('[data-filter]').forEach(btn => {
        btn.addEventListener('click', function() {
            filterKnown(this.dataset.filter);
        });
    });
    
    // Load Friends transcripts
    document.getElementById('loadFriendsBtn')?.addEventListener('click', loadFriendsTranscripts);

    // Cleanup Friends videos
    document.getElementById('cleanupFriendsBtn')?.addEventListener('click', cleanupFriendsVideos);
    
    // Logout
    document.getElementById('logoutBtn')?.addEventListener('click', logout);

    // Backup & Restore
    document.getElementById('backupBtn')?.addEventListener('click', downloadBackup);
    document.getElementById('restoreFile')?.addEventListener('change', restoreBackup);

    // Password toggle functionality
    const passwordToggle = document.getElementById('passwordToggle');
    const passwordInput = document.getElementById('password');
    if (passwordToggle && passwordInput) {
        passwordToggle.addEventListener('click', function() {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            passwordToggle.textContent = type === 'password' ? '👁️' : '🙈';
        });
    }

    // Form submission prevention
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
        });
    }

    // Initialize Google Sign-In
    function initializeGoogleSignIn() {
        if (typeof google !== 'undefined' && google.accounts) {
            try {
                // Get client ID from window variable (set in HTML template)
                const clientId = window.GOOGLE_CLIENT_ID || null;
                
                if (clientId && clientId !== "YOUR_GOOGLE_CLIENT_ID") {
                    google.accounts.id.initialize({
                        client_id: clientId,
                        callback: handleGoogleCredentialResponse,
                        auto_select: false,
                        cancel_on_tap_outside: true
                    });
                    
                    const container = document.getElementById("googleBtnContainer");
                    if (container) {
                        google.accounts.id.renderButton(container, {
                            theme: "outline",
                            size: "large",
                            width: "100%",
                            text: "signin_with",
                            shape: "rectangular",
                            logo_alignment: "left"
                        });
                    }
                } else {
                    // Show a fallback button if client ID is not configured
                    const container = document.getElementById("googleBtnContainer");
                    if (container) {
                        container.innerHTML = `
                            <button class="btn btn-secondary btn-large" style="width: 100%;" onclick="alert('Google girişi için Client ID yapılandırılması gerekiyor. Lütfen yöneticiye başvurun.')">
                                <span style="margin-right: 8px;">🔐</span>
                                Google ile Giriş Yap
                            </button>
                        `;
                    }
                }
            } catch (e) {
                console.warn("Google Sign-In başlatılamadı:", e);
                const container = document.getElementById("googleBtnContainer");
                if (container) {
                    container.innerHTML = `
                        <button class="btn btn-secondary btn-large" style="width: 100%;" onclick="alert('Google girişi şu anda kullanılamıyor.')">
                            <span style="margin-right: 8px;">🔐</span>
                            Google ile Giriş Yap
                        </button>
                    `;
                }
            }
        } else {
            // Google API not loaded yet, wait for it
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initializeGoogleSignIn);
            } else {
                // Try again after a short delay
                setTimeout(initializeGoogleSignIn, 1000);
            }
        }
    }
    
    // Initialize Google Sign-In when Google API is ready
    if (typeof google !== 'undefined') {
        initializeGoogleSignIn();
    } else {
        // Wait for Google API to load
        window.addEventListener('load', function() {
            setTimeout(initializeGoogleSignIn, 500);
        });
    }

    // Inject Vocab Test button dynamically
    const loadWordsBtn = document.getElementById('loadWordsBtn');
    if (loadWordsBtn && !document.getElementById('startVocabTestBtn')) {
        const testBtn = document.createElement('button');
        testBtn.id = 'startVocabTestBtn';
        testBtn.className = 'btn btn-secondary';
        testBtn.textContent = '📊 Seviye Testi';
        testBtn.style.marginLeft = '10px';
        loadWordsBtn.parentNode.insertBefore(testBtn, loadWordsBtn.nextSibling);
        testBtn.addEventListener('click', startVocabTest);
    }
}

// ===== SOCKET.IO SETUP =====

function initializeSocket() {
    socket = io();

    socket.on('connect', function() {
        console.log('Connected to server');
    });

    socket.on('disconnect', function() {
        console.log('Disconnected from server');
    });

    socket.on('user_joined', function(data) {
        console.log('User joined:', data.username);
        updateMembersList(data.members);
    });

    socket.on('user_left', function(data) {
        console.log('User left:', data.username);
        updateMembersList(data.members);
    });

    socket.on('new_message', function(data) {
        addMessageToChat(data);
    });

    socket.on('video_state_changed', function(data) {
        updateVideoState(data);
    });

    socket.on('screen_share_started', function(data) {
        updateMembersList(data.members);
        showNotification(data.username + ' ekran paylaşmaya başladı');
    });

    socket.on('screen_share_stopped', function(data) {
        updateMembersList(data.members);
        showNotification(data.username + ' ekran paylaşmayı durdurdu');
    });

    socket.on('webrtc_offer', function(data) {
        handleWebRTCOffer(data);
    });

    socket.on('webrtc_answer', function(data) {
        handleWebRTCAnswer(data);
    });

    socket.on('webrtc_ice_candidate', function(data) {
        handleICECandidate(data);
    });
}

function cleanupFriendsVideos() {
    if (!confirm('Kelime sayısı 500\'den az olan (hatalı/fallback) Friends bölümleri silinecek. Emin misiniz?')) return;

    fetch('/api/friends/cleanup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert('✅ ' + data.message);
            loadVideos();
        } else {
            alert('❌ Hata: ' + data.error);
        }
    })
    .catch(err => console.error('Error:', err));
}

// ===== FRIENDS EPISODE ANALYSIS =====

// Add event listener for analyze button
document.addEventListener('DOMContentLoaded', function() {
    const analyzeBtn = document.getElementById('analyzeFriendsBtn');
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', analyzeFriendsEpisodes);
    }
});

function analyzeFriendsEpisodes() {
    const seasonSelect = document.getElementById('friendsAnalyzeSeason');
    const selectedSeason = seasonSelect ? seasonSelect.value : 'all';
    
    const statusEl = document.getElementById('friendsAnalysisStatus');
    const summaryEl = document.getElementById('friendsAnalysisSummary');
    const resultsEl = document.getElementById('friendsAnalysisResults');
    const errorEl = document.getElementById('friendsAnalysisError');
    
    // Hide previous results
    summaryEl.style.display = 'none';
    resultsEl.style.display = 'none';
    errorEl.style.display = 'none';
    statusEl.style.display = 'inline-flex';
    
    fetch(`/api/friends/analyze?season=${selectedSeason}`)
    .then(res => res.json())
    .then(data => {
        statusEl.style.display = 'none';
        
        if (data.success) {
            displayFriendsAnalysis(data);
        } else {
            errorEl.textContent = '❌ Hata: ' + data.error;
            errorEl.style.display = 'block';
        }
    })
    .catch(err => {
        statusEl.style.display = 'none';
        errorEl.textContent = '❌ Analiz sırasında hata oluştu: ' + err.message;
        errorEl.style.display = 'block';
        console.error('Friends analysis error:', err);
    });
}

function displayFriendsAnalysis(data) {
    const summaryEl = document.getElementById('friendsAnalysisSummary');
    const resultsEl = document.getElementById('friendsAnalysisResults');
    
    const { episodes, total_levels, level_info, summary, sort_by, sort_order } = data;
    
    // Update summary
    document.getElementById('summaryTotalEpisodes').textContent = summary.total_episodes;
    document.getElementById('summaryTotalWords').textContent = summary.total_words.toLocaleString();
    document.getElementById('summaryAvgWords').textContent = summary.average_words_per_episode;
    
    summaryEl.style.display = 'block';
    
    // Build table header
    const thead = document.getElementById('friendsAnalysisHead');
    let headerHtml = '<tr style="background: #f3f4f6;">';
    headerHtml += '<th style="padding: 10px; text-align: left; border-bottom: 2px solid #e5e7eb; cursor: pointer;" onclick="sortFriendsAnalysis(\'episode\')">Bölüm ⬍</th>';
    headerHtml += '<th style="padding: 10px; text-align: right; border-bottom: 2px solid #e5e7eb; cursor: pointer;" onclick="sortFriendsAnalysis(\'total\')">Toplam ⬍</th>';
    
    // Add level columns
    for (let i = 1; i <= total_levels; i++) {
        const level = level_info[i - 1];
        headerHtml += `<th style="padding: 10px; text-align: right; border-bottom: 2px solid #e5e7eb; cursor: pointer;" onclick="sortFriendsAnalysis('level_${i}')">L${i} ⬍</th>`;
    }
    
    headerHtml += '<th style="padding: 10px; text-align: right; border-bottom: 2px solid #e5e7eb;">Bilinmeyen</th>';
    headerHtml += '</tr>';
    thead.innerHTML = headerHtml;
    
    // Build table body
    const tbody = document.getElementById('friendsAnalysisBody');
    let bodyHtml = '';
    
    episodes.forEach(ep => {
        bodyHtml += '<tr style="border-bottom: 1px solid #e5e7eb;">';
        bodyHtml += `<td style="padding: 8px 10px; font-weight: 500;">${ep.title}</td>`;
        bodyHtml += `<td style="padding: 8px 10px; text-align: right;">${ep.total_words.toLocaleString()}</td>`;
        
        for (let i = 1; i <= total_levels; i++) {
            const count = ep[`level_${i}`] || 0;
            // Highlight higher levels with different colors
            let bgColor = '';
            if (i <= 3) bgColor = '#d1fae5'; // Green for beginner
            else if (i <= 6) bgColor = '#fef3c7'; // Yellow for intermediate
            else bgColor = '#fee2e2'; // Red for advanced
            
            bodyHtml += `<td style="padding: 8px 10px; text-align: right; background: ${count > 0 ? bgColor : 'transparent'};">${count > 0 ? count : '-'}</td>`;
        }
        
        bodyHtml += `<td style="padding: 8px 10px; text-align: right; color: ${ep.unknown_words > 0 ? '#dc2626' : '#059669'};">${ep.unknown_words > 0 ? ep.unknown_words : '-'}</td>`;
        bodyHtml += '</tr>';
    });
    
    tbody.innerHTML = bodyHtml;
    resultsEl.style.display = 'block';
}

// Global sort function
window.sortFriendsAnalysis = function(sortBy) {
    const seasonSelect = document.getElementById('friendsAnalyzeSeason');
    const selectedSeason = seasonSelect ? seasonSelect.value : 'all';
    
    const statusEl = document.getElementById('friendsAnalysisStatus');
    const summaryEl = document.getElementById('friendsAnalysisSummary');
    const resultsEl = document.getElementById('friendsAnalysisResults');
    
    statusEl.style.display = 'inline-flex';
    
    fetch(`/api/friends/analyze?season=${selectedSeason}&sort_by=${sortBy}`)
    .then(res => res.json())
    .then(data => {
        statusEl.style.display = 'none';
        if (data.success) {
            displayFriendsAnalysis(data);
        }
    })
    .catch(err => {
        statusEl.style.display = 'none';
        console.error('Sort error:', err);
    });
}

// ===== WATCH TAB FRIENDS FUNCTIONS =====

// Add event listeners for watch tab
document.addEventListener('DOMContentLoaded', function() {
    const watchEpisodesBtn = document.getElementById('watchFriendsEpisodesBtn');
    if (watchEpisodesBtn) {
        watchEpisodesBtn.addEventListener('click', listFriendsEpisodesForWatch);
    }
    
    const watchAnalyzeBtn = document.getElementById('watchAnalyzeFriendsBtn');
    if (watchAnalyzeBtn) {
        watchAnalyzeBtn.addEventListener('click', analyzeFriendsForWatch);
    }
});

function listFriendsEpisodesForWatch() {
    const seasonSelect = document.getElementById('watchFriendsSeason');
    const selectedSeason = seasonSelect ? seasonSelect.value : '1';
    
    const statusEl = document.getElementById('watchFriendsStatus');
    const episodesEl = document.getElementById('watchFriendsEpisodes');
    
    statusEl.style.display = 'inline-flex';
    episodesEl.style.display = 'none';
    
    // Friends season episode names
    const friendsEpisodes = {
        1: ["Pilot", "The One with the Sonogram at the End", "The One Hundred", "The One with Two Parts: Part 1", "The One with Two Parts: Part 2", "The One with the Butt", "The One with the Blackmail", "The One Where Nap-Land is Closed", "The One Where Underdog Gets Away", "The One with the Monkey", "The One with Mrs. Bing", "The One with the Dozen Lasagnas", "The One with Rachael Green", "The One with Two Rooms", "The One with the Stoned Guy", "The One with Two Parts: Part 1", "The One with the Bullies", "The One with a Loser", "The One with the Fake Monica", "The One with the Ick Factor", "The One with the Thumb", "The One with the Boobies", "The One with the Curtains", "The One with the Rumor"],
        2: 24, 3: 25, 4: 24, 5: 24, 6: 25, 7: 24, 8: 24, 9: 24, 10: 18
    };
    
    const episodesCount = friendsEpisodes[selectedSeason]?.length || friendsEpisodes[selectedSeason] || 24;
    
    let html = '';
    for (let i = 1; i <= episodesCount; i++) {
        let epName = `Bölüm ${i}`;
        if (Array.isArray(friendsEpisodes[selectedSeason]) && i <= friendsEpisodes[selectedSeason].length) {
            epName = friendsEpisodes[selectedSeason][i - 1];
        }
        
        html += `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 15px; border-bottom: 1px solid #e5e7eb; hover: background: #f9fafb;">
                <div>
                    <span style="font-weight: 600;">S${selectedSeason}E${i.toString().padStart(2, '0')}</span>
                    <span style="color: #6b7280; margin-left: 10px;">${epName}</span>
                </div>
                <button class="btn btn-small btn-primary" onclick="createFriendsRoom(${selectedSeason}, ${i})">
                    🚪 Oda Kur
                </button>
            </div>
        `;
    }
    
    episodesEl.innerHTML = html;
    statusEl.style.display = 'none';
    episodesEl.style.display = 'block';
}

window.createFriendsRoom = function(season, episode) {
    if (!requireLogin(() => createFriendsRoom(season, episode), 'Oda oluşturmak için giriş yapmanız gerekiyor.')) {
        return;
    }
    
    const roomName = `Friends S${season}E${episode}`;
    const videoTitle = `Friends Season ${season} Episode ${episode}`;
    const videoUrl = `https://www.imdb.com/title/tt0108778/`;
    
    fetch('/api/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            room_name: roomName,
            user_id: currentUser.user_id,
            video_url: videoUrl,
            video_title: videoTitle
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert(`✅ Oda oluşturuldu: ${roomName}\nŞimdi odanıza katılabilirsiniz!`);
            joinRoom(data.room_id);
            loadRooms();
        } else {
            alert('❌ Hata: ' + data.error);
        }
    })
    .catch(err => {
        console.error('Create room error:', err);
        alert('Oda oluşturulurken hata oluştu');
    });
};

function analyzeFriendsForWatch() {
    const seasonSelect = document.getElementById('watchAnalyzeSeason');
    const selectedSeason = seasonSelect ? seasonSelect.value : 'all';
    
    const statusEl = document.getElementById('watchFriendsAnalysisStatus');
    const summaryEl = document.getElementById('watchFriendsAnalysisSummary');
    const resultsEl = document.getElementById('watchFriendsAnalysisResults');
    const errorEl = document.getElementById('watchFriendsAnalysisError');
    
    summaryEl.style.display = 'none';
    resultsEl.style.display = 'none';
    errorEl.style.display = 'none';
    statusEl.style.display = 'inline-flex';
    
    fetch(`/api/friends/analyze?season=${selectedSeason}`)
    .then(res => res.json())
    .then(data => {
        statusEl.style.display = 'none';
        
        if (data.success) {
            displayWatchFriendsAnalysis(data);
        } else {
            errorEl.textContent = '❌ Hata: ' + data.error;
            errorEl.style.display = 'block';
        }
    })
    .catch(err => {
        statusEl.style.display = 'none';
        errorEl.textContent = '❌ Analiz sırasında hata oluştu: ' + err.message;
        errorEl.style.display = 'block';
        console.error('Watch friends analysis error:', err);
    });
}

function displayWatchFriendsAnalysis(data) {
    const summaryEl = document.getElementById('watchFriendsAnalysisSummary');
    const resultsEl = document.getElementById('watchFriendsAnalysisResults');
    
    const { episodes, total_levels, level_info, summary } = data;
    
    // Update summary
    document.getElementById('watchSummaryEpisodes').textContent = summary.total_episodes;
    document.getElementById('watchSummaryWords').textContent = summary.total_words.toLocaleString();
    document.getElementById('watchSummaryAvg').textContent = summary.average_words_per_episode;
    
    summaryEl.style.display = 'block';
    
    // Build table header
    const thead = document.getElementById('watchFriendsAnalysisHead');
    let headerHtml = '<tr style="background: #f3f4f6;">';
    headerHtml += '<th style="padding: 8px; text-align: left; border-bottom: 2px solid #e5e7eb;">Bölüm</th>';
    headerHtml += '<th style="padding: 8px; text-align: right; border-bottom: 2px solid #e5e7eb;">Toplam</th>';
    
    // Add level columns (limit to first 5 for watch tab)
    const maxLevels = Math.min(total_levels, 5);
    for (let i = 1; i <= maxLevels; i++) {
        headerHtml += `<th style="padding: 8px; text-align: right; border-bottom: 2px solid #e5e7eb;">L${i}</th>`;
    }
    
    headerHtml += '<th style="padding: 8px; text-align: right; border-bottom: 2px solid #e5e7eb;">?</th>';
    headerHtml += '</tr>';
    thead.innerHTML = headerHtml;
    
    // Build table body
    const tbody = document.getElementById('watchFriendsAnalysisBody');
    let bodyHtml = '';
    
    episodes.forEach(ep => {
        bodyHtml += '<tr style="border-bottom: 1px solid #e5e7eb;">';
        bodyHtml += `<td style="padding: 8px; font-weight: 500;">${ep.title}</td>`;
        bodyHtml += `<td style="padding: 8px; text-align: right;">${ep.total_words.toLocaleString()}</td>`;
        
        for (let i = 1; i <= maxLevels; i++) {
            const count = ep[`level_${i}`] || 0;
            bodyHtml += `<td style="padding: 8px; text-align: right; ${count > 0 ? 'background: #d1fae5;' : ''}">${count > 0 ? count : '-'}</td>`;
        }
        
        bodyHtml += `<td style="padding: 8px; text-align: right; color: ${ep.unknown_words > 0 ? '#dc2626' : '#059669'};">${ep.unknown_words > 0 ? ep.unknown_words : '-'}</td>`;
        bodyHtml += '</tr>';
    });
    
    tbody.innerHTML = bodyHtml;
    resultsEl.style.display = 'block';
}

// ===== USER MANAGEMENT =====

function showError(message) {
    const errorEl = document.getElementById('loginError');
    const successEl = document.getElementById('loginSuccess');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = 'block';
    }
    if (successEl) {
        successEl.style.display = 'none';
    }
    // Auto-hide after 5 seconds
    setTimeout(() => {
        if (errorEl) errorEl.style.display = 'none';
    }, 5000);
}

function showSuccess(message) {
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

function setButtonLoading(buttonId, loading) {
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

function loginUser() {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const rememberMe = document.getElementById('rememberMe')?.checked;
    
    // Hide previous messages
    showError('');
    
    if (!username || !password) {
        showError('Lütfen kullanıcı adı ve şifre girin');
        return;
    }

    setButtonLoading('loginBtn', true);

    fetch('/api/auth/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username: username, password: password })
    })
    .then(res => res.json())
    .then(data => {
        setButtonLoading('loginBtn', false);
        if (data.success) {
            currentUser = data;
            window.currentUser = data; // Make available to inline scripts
            if (rememberMe) {
                localStorage.setItem('currentUser', JSON.stringify(currentUser));
                sessionStorage.removeItem('currentUser');
            } else {
                sessionStorage.setItem('currentUser', JSON.stringify(currentUser));
                localStorage.removeItem('currentUser');
            }
            showSuccess('Giriş başarılı! Yönlendiriliyorsunuz...');
            setTimeout(() => {
                showAppSection();
                switchTab('rooms');
                loadStats();
                // Execute any pending action after login
                executePendingAction();
            }, 500);
        } else {
            showError(data.error || 'Giriş yapılamadı. Lütfen bilgilerinizi kontrol edin.');
        }
    })
    .catch(err => {
        setButtonLoading('loginBtn', false);
        console.error('Error:', err);
        showError('Bağlantı hatası. Lütfen tekrar deneyin.');
    });
}

function registerUser() {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    
    // Hide previous messages
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

    fetch('/api/auth/register', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username: username, password: password })
    })
    .then(res => res.json())
    .then(data => {
        setButtonLoading('registerBtn', false);
        if (data.success) {
            showSuccess('✅ ' + (data.message || 'Kayıt başarılı! Giriş yapılıyor...'));
            // Otomatik giriş yap
            setTimeout(() => {
                loginUser();
            }, 1000);
        } else {
            showError('❌ ' + (data.error || 'Kayıt yapılamadı'));
        }
    })
    .catch(err => {
        setButtonLoading('registerBtn', false);
        console.error('Error:', err);
        showError('Kayıt sırasında bir hata oluştu. Lütfen tekrar deneyin.');
    });
}

function handleGoogleCredentialResponse(response) {
    // Show loading state
    const errorEl = document.getElementById('loginError');
    const successEl = document.getElementById('loginSuccess');
    if (successEl) {
        successEl.textContent = 'Google ile giriş yapılıyor...';
        successEl.style.display = 'block';
    }
    if (errorEl) {
        errorEl.style.display = 'none';
    }

    fetch('/api/auth/google', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ token: response.credential })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            currentUser = data;
            window.currentUser = data; // Make available to inline scripts
            
            const rememberMe = document.getElementById('rememberMe')?.checked;
            if (rememberMe) {
                localStorage.setItem('currentUser', JSON.stringify(currentUser));
                sessionStorage.removeItem('currentUser');
            } else {
                sessionStorage.setItem('currentUser', JSON.stringify(currentUser));
                localStorage.removeItem('currentUser');
            }
            
            if (successEl) {
                successEl.textContent = 'Google ile giriş başarılı! Yönlendiriliyorsunuz...';
            }
            
            setTimeout(() => {
                showAppSection();
                switchTab('rooms');
                loadStats();
                // Execute any pending action after login
                executePendingAction();
            }, 500);
        } else {
            showError('❌ Google girişi başarısız: ' + (data.error || 'Bilinmeyen hata'));
        }
    })
    .catch(err => {
        console.error('Google auth error:', err);
        showError('Google ile giriş yapılırken bir hata oluştu. Lütfen tekrar deneyin.');
    });
}

function logout() {
    window.currentUser = null; // Clear from window object
    if (roomsInterval) {
        clearInterval(roomsInterval);
        roomsInterval = null;
    }
    localStorage.removeItem('currentUser');
    sessionStorage.removeItem('currentUser');
    currentUser = null;
    currentRoom = null;
    if (socket) {
        socket.disconnect();
    }
    document.getElementById('loginSection').classList.add('active');
    document.getElementById('appSection').style.display = 'none';
}

function showAppSection() {
    document.getElementById('loginSection').classList.remove('active');
    document.getElementById('appSection').classList.add('active');
    document.getElementById('appSection').style.display = 'block';
}

function showLoginSection() {
    document.getElementById('appSection').classList.remove('active');
    document.getElementById('loginSection').classList.add('active');
    document.getElementById('loginSection').style.display = 'block';
}
window.showLoginSection = showLoginSection; // Make available globally

// Helper function to require login before executing an action
let pendingActionAfterLogin = null;

function requireLogin(callback, message = 'Bu işlem için giriş yapmanız gerekiyor.') {
    if (currentUser && currentUser.user_id) {
        // User is logged in, execute callback immediately
        if (callback) callback();
        return true;
    } else {
        // User is not logged in, show message and redirect to login
        if (message) {
            alert(message);
        }
        pendingActionAfterLogin = callback;
        showLoginSection();
        return false;
    }
}

// Execute pending action after successful login
function executePendingAction() {
    if (pendingActionAfterLogin) {
        const action = pendingActionAfterLogin;
        pendingActionAfterLogin = null;
        if (typeof action === 'function') {
            action();
        }
    }
}

// ===== TAB SWITCHING =====

function switchTab(tabName) {
    if (roomsInterval) {
        clearInterval(roomsInterval);
        roomsInterval = null;
    }

    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.style.display = 'none';
    });

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    const tabElement = document.getElementById(tabName + 'Tab');
    if (tabElement) {
        tabElement.style.display = 'block';
    }

    const tabBtn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
    if (tabBtn) {
        tabBtn.classList.add('active');
    }

    if (tabName === 'rooms') {
        loadRooms();
        roomsInterval = setInterval(loadRooms, 5000);
    } else if (tabName === 'learn') {
        loadWords();
        loadStats();
        loadVideos();
    } else if (tabName === 'profile') {
        loadUserProfile();
    }
}

// ===== ROOM MANAGEMENT =====

function loadRooms() {
    fetch('/api/rooms')
    .then(res => {
        return res.json();
    })
    .then(data => {
        if (data.success) {
            displayRooms(data.rooms);
        } else {
            console.error('Load rooms error:', data.error);
        }
    })
    .catch(err => console.error('❌ Error loading rooms:', err));
}

function displayRooms(rooms) {
    const roomsList = document.getElementById('roomsList');
    
    if (rooms.length === 0) {
        roomsList.innerHTML = '<p>Aktif oda yok. Yeni oda oluşturun!</p>';
        return;
    }

    roomsList.innerHTML = rooms.map(room => `
        <div class="room-card">
            <h3>${room.room_name}</h3>
            <p>${room.video_title || 'Video seçilmemiş'}</p>
            <p style="color: #6b7280; font-size: 0.85em;">Oluşturan: ${room.creator_name}</p>
            <div class="room-meta">
                <span class="room-members-count">👥 ${room.member_count} kişi</span>
                <button class="btn btn-primary room-join-btn" data-room-id="${room.id}">
                    Katıl
                </button>
            </div>
        </div>
    `).join('');
    
    // Add event listeners to join buttons
    document.querySelectorAll('.room-join-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            joinRoom(parseInt(this.dataset.roomId));
        });
    });
}

function createNewRoom() {
    const roomName = document.getElementById('roomName').value.trim();
    const videoUrl = document.getElementById('videoUrl').value.trim();
    const videoTitle = document.getElementById('videoTitle').value.trim();

    console.log('Creating room:', { roomName, videoUrl, videoTitle, userId: currentUser?.user_id });

    if (!roomName) {
        alert('Lütfen oda adı girin');
        return;
    }

    if (!currentUser || !currentUser.user_id) {
        alert('Lütfen önce giriş yapın');
        return;
    }

    fetch('/api/rooms', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            room_name: roomName,
            user_id: currentUser.user_id,
            video_url: videoUrl,
            video_title: videoTitle
        })
    })
    .then(res => {
        console.log('Create room response status:', res.status);
        return res.json();
    })
    .then(data => {
        console.log('Create room response:', data);
        if (data.success) {
            alert('✅ Oda oluşturuldu!');
            joinRoom(data.room_id);
            loadRooms();
            document.getElementById('roomName').value = 'Benim Odası';
            document.getElementById('videoUrl').value = '';
            document.getElementById('videoTitle').value = '';
        } else {
            alert('❌ Hata: ' + (data.error || 'Oda oluşturulamadı'));
        }
    })
    .catch(err => {
        console.error('❌ Create room error:', err);
        alert('Oda oluşturulurken hata oluştu: ' + err.message);
    });
}

function joinRoom(roomId) {
    console.log('Joining room:', roomId, 'currentUser:', currentUser);
    
    if (!requireLogin(() => joinRoom(roomId), 'Odaya katılmak için giriş yapmanız gerekiyor.')) {
        return;
    }

    // Eğer zaten bir odadaysak ve farklı bir odaya geçiyorsak, önce eskisinden çıkalım
    if (currentRoom && currentRoom !== roomId) {
        console.log('Switching rooms, leaving room:', currentRoom);
        leaveRoom(); // Bu işlem asenkron ama UI hemen güncellendiği için sorun olmaz
    }

    fetch(`/api/rooms/${roomId}/join`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: currentUser.user_id
        })
    })
    .then(res => {
        console.log('Join room response status:', res.status);
        return res.json();
    })
    .then(data => {
        console.log('Join room data:', data);
        if (data.success) {
            currentRoom = roomId;
            console.log('✅ Odaya katıldı, room:', currentRoom);
            
            // Socket emit
            socket.emit('join_room', {
                room_id: roomId,
                user_id: currentUser.user_id,
                username: currentUser.username
            });

            loadRoomDetails(roomId);
            loadRoomVideoStats(roomId); // Load stats when joining
            switchTab('watch');
        } else {
            alert('❌ Hata: ' + (data.error || data.message || 'Bilinmeyen hata'));
        }
    })
    .catch(err => {
        console.error('❌ Join room error:', err);
        alert('❌ Odaya katılırken hata oluştu: ' + err.message);
    });
}

function loadRoomDetails(roomId) {
    fetch(`/api/rooms/${roomId}`)
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            displayRoomDetails(roomId, data.members || [], data.messages || [], data.room);
        } else {
            alert('Oda detayları yüklenemedi: ' + (data.error || 'Bilinmeyen hata'));
        }
    })
    .catch(err => {
        console.error('Error loading room details:', err);
        alert('Oda detayları yüklenirken hata oluştu');
    });
}

function loadRoomVideoStats(roomId) {
    if (!currentUser) return;
    
    fetch(`/api/rooms/${roomId}/stats?user_id=${currentUser.user_id}`)
    .then(res => res.json())
    .then(data => {
        const statsContainer = document.getElementById('roomVideoStats');
        if (data.success && data.stats) {
            const s = data.stats;
            statsContainer.style.display = 'block';
            statsContainer.innerHTML = `
                <div style="background: #f0f9ff; border: 1px solid #bae6fd; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <h4 style="margin-top: 0; color: #0369a1;">📊 Film Kelime Analizi</h4>
                    <div style="display: flex; justify-content: space-between; margin: 10px 0; font-size: 0.9em;">
                        <span>Toplam: <strong>${s.total}</strong></span>
                        <span style="color: #059669;">Bilinen: <strong>${s.known}</strong></span>
                        <span style="color: #dc2626;">Bilinmeyen: <strong>${s.unknown}</strong></span>
                    </div>
                    <div style="background: #e0e7ff; height: 8px; border-radius: 4px; overflow: hidden; margin-bottom: 10px;">
                        <div style="width: ${s.percentage}%; background: #059669; height: 100%;"></div>
                    </div>
                    <button id="studyUnknownBtn" class="btn btn-primary" style="width: 100%; font-size: 0.9em;">
                        🧠 Bilinmeyen ${s.unknown} Kelimeye Çalış
                    </button>
                </div>
            `;
            
            document.getElementById('studyUnknownBtn').addEventListener('click', () => {
                studyRoomWords(roomId);
            });
        } else {
            statsContainer.style.display = 'none';
        }
    })
    .catch(err => console.error('Error loading stats:', err));
}

function studyRoomWords(roomId) {
    fetch(`/api/rooms/${roomId}/words?user_id=${currentUser.user_id}&status=unknown`)
    .then(res => res.json())
    .then(data => {
        if (data.success && data.words.length > 0) {
            showStudyModal(data.words);
        } else {
            alert('Çalışılacak bilinmeyen kelime bulunamadı!');
        }
    });
}

function showStudyModal(words) {
    // Create modal if not exists
    let modal = document.getElementById('studyModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'studyModal';
        modal.style.cssText = `position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 10000; display: flex; justify-content: center; align-items: center;`;
        document.body.appendChild(modal);
    }
    
    modal.innerHTML = `
        <div style="background: white; width: 90%; max-width: 800px; max-height: 90vh; overflow-y: auto; padding: 20px; border-radius: 12px; position: relative;">
            <button onclick="document.getElementById('studyModal').remove()" style="position: absolute; right: 15px; top: 15px; border: none; background: none; font-size: 1.5em; cursor: pointer;">✕</button>
            <h2 style="margin-bottom: 20px;">📝 Kelime Çalışma Modu</h2>
            <div id="studyWordsList" class="words-grid"></div>
        </div>
    `;
    
    // Reuse displayWords logic but render into modal
    const tempContainer = document.getElementById('wordsList'); // Save original ref
    const modalList = document.getElementById('studyWordsList');
    
    // Temporarily hijack displayWords target or create a custom renderer
    // Let's use a custom renderer based on displayWords logic for simplicity
    modalList.innerHTML = words.map(word => `
        <div class="word-card" onclick="this.classList.toggle('flipped')">
            <div class="word-card-inner">
                <div class="word-card-front">
                    <div class="word-text">${word.word}</div>
                    <div class="word-status">Çevir</div>
                </div>
                <div class="word-card-back">
                    <div class="word-definition">Sıklık: ${word.frequency}</div>
                    <button class="btn btn-small btn-secondary" style="margin-top: 10px; background: white; color: #059669;" onclick="event.stopPropagation(); markWordFromStudy(${word.id}, true, this)">
                        ✅ Öğrendim
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

window.markWordFromStudy = function(wordId, known, btnElement) {
    toggleWordStatus(wordId, known);
    // Visual feedback
    const card = btnElement.closest('.word-card');
    card.style.opacity = '0.5';
    card.style.pointerEvents = 'none';
}

function displayRoomDetails(roomId, members, messages, roomInfo) {
    const watchContainer = document.getElementById('watchContainer');
    const noRoomSelected = document.getElementById('noRoomSelected');
    const currentRoomName = document.getElementById('currentRoomName');
    const currentVideoTitle = document.getElementById('currentVideoTitle');
    
    if (watchContainer) {
        watchContainer.style.display = 'grid';
    }
    if (noRoomSelected) {
        noRoomSelected.style.display = 'none';
    }
    if (currentRoomName && roomInfo) {
        currentRoomName.textContent = roomInfo.room_name;
    }
    if (currentVideoTitle && roomInfo) {
        currentVideoTitle.textContent = `Video: ${roomInfo.video_title || 'Seçilmemiş'}`;
    }
    
    updateMembersList(members);
    displayChatMessages(messages);
    
    // Add stats container if not exists
    if (!document.getElementById('roomVideoStats')) {
        const sidebar = document.querySelector('.sidebar');
        const statsDiv = document.createElement('div');
        statsDiv.id = 'roomVideoStats';
        statsDiv.style.display = 'none';
        sidebar.insertBefore(statsDiv, sidebar.firstChild);
    }
}

function updateMembersList(members) {
    const membersList = document.getElementById('membersList');
    
    if (members.length === 0) {
        membersList.innerHTML = '<p>Üye yok</p>';
        return;
    }

    membersList.innerHTML = members.map(member => `
        <div class="member-item ${member.is_screen_sharing ? 'sharing' : ''}">
            <div class="member-avatar">${member.username.charAt(0).toUpperCase()}</div>
            <span class="member-name">${member.username}</span>
            ${member.is_screen_sharing ? '<span class="member-status">📺 Paylaşıyor</span>' : ''}
        </div>
    `).join('');
}

function leaveRoom() {
    if (!currentRoom) return;

    socket.emit('leave_room', {
        room_id: currentRoom,
        user_id: currentUser.user_id
    });

    fetch(`/api/rooms/${currentRoom}/leave`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: currentUser.user_id
        })
    })
    .then(res => res.json())
    .then(data => {
        // currentRoom = null; // leaveRoom çağrıldığında currentRoom'u hemen null yapmayalım, joinRoom mantığı için
        document.getElementById('watchContainer').style.display = 'none';
        document.getElementById('noRoomSelected').style.display = 'block';
        switchTab('rooms');
    })
    .catch(err => console.error('Error:', err));
}

function shareRoom() {
    if (!currentRoom) {
        alert('Lütfen önce bir odaya katılın');
        return;
    }

    // Get room invitation link
    const inviteLink = `${window.location.origin}?room=${currentRoom}`;
    
    // Create a modal with share options
    const modal = document.createElement('div');
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
    `;
    
    const content = document.createElement('div');
    content.style.cssText = `
        background: white;
        border-radius: 12px;
        padding: 30px;
        max-width: 500px;
        width: 90%;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
    `;
    
    content.innerHTML = `
        <h2 style="margin-bottom: 20px; color: #1f2937;">🔗 Odayı Paylaş</h2>
        
        <div style="background: #f3f4f6; padding: 15px; border-radius: 8px; margin-bottom: 20px; word-break: break-all;">
            <code style="font-family: monospace; color: #3b82f6; font-size: 0.9em;">${inviteLink}</code>
        </div>
        
        <div style="display: flex; gap: 10px; margin-bottom: 20px;">
            <button id="copyLinkBtn" class="btn btn-primary" style="flex: 1;">📋 Linki Kopyala</button>
            <button id="shareNativeBtn" class="btn btn-secondary" style="flex: 1;">🔀 Paylaş</button>
        </div>
        
        <div style="background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 12px; margin-bottom: 20px; font-size: 0.9em;">
            <strong>💡 İpucu:</strong> Arkadaşlarını davet etmek için linki kopyala ve gönder!
        </div>
        
        <button id="closeShareModalBtn" class="btn btn-secondary" style="width: 100%;">Kapat</button>
    `;
    
    modal.appendChild(content);
    document.body.appendChild(modal);
    
    // Copy link button
    document.getElementById('copyLinkBtn').addEventListener('click', function() {
        navigator.clipboard.writeText(inviteLink).then(() => {
            this.textContent = '✅ Kopyalandı!';
            setTimeout(() => {
                this.textContent = '📋 Linki Kopyala';
            }, 2000);
        }).catch(() => {
            alert('Link kopyalanamadı');
        });
    });
    
    // Native share
    document.getElementById('shareNativeBtn').addEventListener('click', function() {
        if (navigator.share) {
            navigator.share({
                title: 'Watch Together',
                text: 'Beni film izleme odasında davet ediyor!',
                url: inviteLink
            }).catch(err => console.error('Error sharing:', err));
        } else {
            alert('Tarayıcı paylaşma özelliğini desteklemiyor');
        }
    });
    
    // Close button
    document.getElementById('closeShareModalBtn').addEventListener('click', function() {
        modal.remove();
    });
    
    // Close on outside click
    modal.addEventListener('click', function(e) {
        if (e.target === this) {
            this.remove();
        }
    });
}

// ===== CHAT FUNCTIONALITY =====

function sendMessage() {
    if (!currentRoom) return;

    const input = document.getElementById('chatInput');
    const message = input.value.trim();

    if (!message) return;

    socket.emit('send_message', {
        room_id: currentRoom,
        user_id: currentUser.user_id,
        username: currentUser.username,
        message: message
    });

    input.value = '';
}

function handleChatKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

function addMessageToChat(data) {
    const timestamp = new Date(data.timestamp).toLocaleTimeString('tr-TR');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message';
    messageDiv.innerHTML = `
        <div class="chat-message-author">${data.username}</div>
        <div class="chat-message-text">${escapeHtml(data.message)}</div>
        <div class="chat-message-time">${timestamp}</div>
    `;

    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function displayChatMessages(messages) {
    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.innerHTML = '';

    messages.forEach(msg => {
        const timestamp = new Date(msg.created_date).toLocaleTimeString('tr-TR');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message';
        messageDiv.innerHTML = `
            <div class="chat-message-author">${msg.username}</div>
            <div class="chat-message-text">${escapeHtml(msg.message)}</div>
            <div class="chat-message-time">${timestamp}</div>
        `;
        messagesContainer.appendChild(messageDiv);
    });

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// ===== VIDEO SYNCHRONIZATION =====

const videoElement = document.getElementById('videoElement');

videoElement.addEventListener('play', function() {
    if (currentRoom && socket) {
        socket.emit('video_sync', {
            room_id: currentRoom,
            user_id: currentUser.user_id,
            action: 'play',
            current_time: videoElement.currentTime
        });
    }
});

videoElement.addEventListener('pause', function() {
    if (currentRoom && socket) {
        socket.emit('video_sync', {
            room_id: currentRoom,
            user_id: currentUser.user_id,
            action: 'pause',
            current_time: videoElement.currentTime
        });
    }
});

videoElement.addEventListener('seeked', function() {
    if (currentRoom && socket) {
        socket.emit('video_sync', {
            room_id: currentRoom,
            user_id: currentUser.user_id,
            action: 'seek',
            current_time: videoElement.currentTime
        });
    }
});

function updateVideoState(data) {
    if (data.user_id === currentUser.user_id) return;

    const tolerance = 0.5; // 0.5 saniye tolerans

    if (data.action === 'play') {
        if (Math.abs(videoElement.currentTime - data.current_time) > tolerance) {
            videoElement.currentTime = data.current_time;
        }
        if (videoElement.paused) {
            videoElement.play();
        }
    } else if (data.action === 'pause') {
        videoElement.pause();
        if (Math.abs(videoElement.currentTime - data.current_time) > tolerance) {
            videoElement.currentTime = data.current_time;
        }
    } else if (data.action === 'seek') {
        videoElement.currentTime = data.current_time;
    }
}

// ===== SCREEN SHARING =====

function toggleScreenShare() {
    if (!currentRoom || !socket) return;

    if (isScreenSharing) {
        stopScreenShare();
    } else {
        startScreenShare();
    }
}

function startScreenShare() {
    if (navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) {
        navigator.mediaDevices.getDisplayMedia({
            video: { cursor: 'always' },
            audio: {
                echoCancellation: false,
                noiseSuppression: false,
                autoGainControl: false
            },
            systemAudio: 'include'
        })
        .then(stream => {
            isScreenSharing = true;
            document.getElementById('screenShareBtn').textContent = '⏹️ Ekran Paylaşmayı Durdur';
            document.getElementById('screenShareBtn').style.background = '#ef4444';

            // Show local screen share
            const screenShareArea = document.getElementById('screenShareArea');
            const videoEl = document.getElementById('videoElement');
            
            if (videoEl) {
                videoEl.style.display = 'none';
            }
            
            if (screenShareArea) {
                screenShareArea.style.display = 'flex';
                screenShareArea.style.justifyContent = 'center';
                screenShareArea.style.alignItems = 'center';
                screenShareArea.style.flexDirection = 'column';
                screenShareArea.style.gap = '10px';
                
                // Create video element for screen share if not exists
                let screenVideo = document.getElementById('screenVideo');
                if (!screenVideo) {
                    screenVideo = document.createElement('video');
                    screenVideo.id = 'screenVideo';
                    screenVideo.autoplay = true;
                    screenVideo.muted = true; // Avoid echo for sharer
                    screenVideo.style.width = '100%';
                    screenVideo.style.height = '100%';
                    screenVideo.style.objectFit = 'contain';
                    screenShareArea.innerHTML = '';
                    screenShareArea.appendChild(screenVideo);
                }
                
                screenVideo.srcObject = stream;
            }

            socket.emit('screen_share_start', {
                room_id: currentRoom,
                user_id: currentUser.user_id,
                username: currentUser.username
            });

            setupPeerConnection(stream);

            stream.getVideoTracks()[0].onended = function() {
                stopScreenShare();
            };
        })
        .catch(err => {
            console.error('Ekran paylaşma hatası:', err);
            alert('Ekran paylaşma başarısız: ' + err.message);
        });
    } else {
        alert('Tarayıcınız ekran paylaşmayı desteklemiyor');
    }
}

function stopScreenShare() {
    isScreenSharing = false;
    document.getElementById('screenShareBtn').textContent = '📺 Ekran Paylaş';
    document.getElementById('screenShareBtn').style.background = '';

    // Hide screen share area and show video player
    const screenShareArea = document.getElementById('screenShareArea');
    const videoEl = document.getElementById('videoElement');
    
    if (screenShareArea) {
        screenShareArea.style.display = 'none';
    }
    
    if (videoEl) {
        videoEl.style.display = 'block';
    }

    if (peerConnection) {
        peerConnection.close();
        peerConnection = null;
    }

    socket.emit('screen_share_stop', {
        room_id: currentRoom,
        user_id: currentUser.user_id,
        username: currentUser.username
    });
}

function setupPeerConnection(stream) {
    peerConnection = new RTCPeerConnection({
        iceServers: [
            { urls: ['stun:stun.l.google.com:19302'] },
            { urls: ['stun:stun1.l.google.com:19302'] }
        ]
    });

    stream.getTracks().forEach(track => {
        peerConnection.addTrack(track, stream);
    });

    peerConnection.onicecandidate = (event) => {
        if (event.candidate) {
            socket.emit('webrtc_ice_candidate', {
                room_id: currentRoom,
                user_id: currentUser.user_id,
                candidate: event.candidate
            });
        }
    };

    peerConnection.createOffer().then(offer => {
        return peerConnection.setLocalDescription(offer);
    }).then(() => {
        socket.emit('webrtc_offer', {
            room_id: currentRoom,
            user_id: currentUser.user_id,
            offer: peerConnection.localDescription
        });
    }).catch(err => console.error('Offer error:', err));
}

function handleWebRTCOffer(data) {
    if (!peerConnection) {
        peerConnection = new RTCPeerConnection({
            iceServers: [
                { urls: ['stun:stun.l.google.com:19302'] },
                { urls: ['stun:stun1.l.google.com:19302'] }
            ]
        });

        // Handle incoming stream
        peerConnection.ontrack = function(event) {
            const screenShareArea = document.getElementById('screenShareArea');
            const videoEl = document.getElementById('videoElement');
            
            if (videoEl) {
                videoEl.style.display = 'none';
            }
            
            if (screenShareArea) {
                screenShareArea.style.display = 'flex';
                screenShareArea.style.justifyContent = 'center';
                screenShareArea.style.alignItems = 'center';
                screenShareArea.style.flexDirection = 'column';
                screenShareArea.style.gap = '10px';
                
                let screenVideo = document.getElementById('screenVideo');
                if (!screenVideo) {
                    screenVideo = document.createElement('video');
                    screenVideo.id = 'screenVideo';
                    screenVideo.autoplay = true;
                    screenVideo.controls = true;
                    screenVideo.muted = false;
                    screenVideo.style.width = '100%';
                    screenVideo.style.height = '100%';
                    screenVideo.style.objectFit = 'contain';
                    screenShareArea.innerHTML = '';
                    screenShareArea.appendChild(screenVideo);
                }
                
                screenVideo.srcObject = event.streams[0];
            }
        };
    }

    const offer = new RTCSessionDescription(data.offer);
    peerConnection.setRemoteDescription(offer).then(() => {
        return peerConnection.createAnswer();
    }).then(answer => {
        return peerConnection.setLocalDescription(answer);
    }).then(() => {
        socket.emit('webrtc_answer', {
            room_id: currentRoom,
            user_id: currentUser.user_id,
            answer: peerConnection.localDescription
        });
    }).catch(err => console.error('Answer error:', err));
}

function handleWebRTCAnswer(data) {
    const answer = new RTCSessionDescription(data.answer);
    peerConnection.setRemoteDescription(answer).catch(err => console.error('Answer error:', err));
}

function handleICECandidate(data) {
    if (peerConnection) {
        peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate))
            .catch(err => console.error('ICE error:', err));
    }
}

// ===== LEARNING FEATURES =====

function processVideos() {
    const btn = document.getElementById('processBtn');
    const status = document.getElementById('processingStatus');
    const result = document.getElementById('processResult');

    btn.disabled = true;
    status.style.display = 'block';
    result.style.display = 'none';

    fetch('/api/process-videos', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: currentUser.user_id
        })
    })
    .then(res => res.json())
    .then(data => {
        status.style.display = 'none';
        
        if (data.success) {
            result.innerHTML = `
                <div style="background: #d1fae5; border: 1px solid #6ee7b7; padding: 15px; border-radius: 8px; color: #047857;">
                    <strong>✅ Başarılı!</strong><br>
                    ${data.videos_processed} video işlendi<br>
                    ${data.new_words_found} yeni kelime bulundu
                </div>
            `;
            result.style.display = 'block';
            setTimeout(() => loadWords(), 500);
            setTimeout(() => loadVideos(), 500);
        } else {
            result.innerHTML = `<div style="background: #fee2e2; border: 1px solid #fca5a5; padding: 15px; border-radius: 8px; color: #dc2626;">❌ Hata: ${data.error}</div>`;
            result.style.display = 'block';
        }
    })
    .catch(err => {
        status.style.display = 'none';
        result.innerHTML = '<div style="background: #fee2e2; padding: 15px; border-radius: 8px; color: #dc2626;">❌ İstek hatası</div>';
        result.style.display = 'block';
        console.error('Error:', err);
    })
    .finally(() => {
        btn.disabled = false;
    });
}

function processVideoUrl() {
    const urlInput = document.getElementById('learnVideoUrl');
    const url = urlInput.value.trim();
    const btn = document.getElementById('processUrlBtn');
    const status = document.getElementById('urlProcessingStatus');
    const result = document.getElementById('urlProcessResult');

    if (!url) {
        alert('Lütfen bir URL girin');
        return;
    }

    if (!requireLogin(() => processVideoUrl(), 'Video işlemek için giriş yapmanız gerekiyor.')) {
        return;
    }

    btn.disabled = true;
    status.style.display = 'block';
    result.style.display = 'none';

    fetch('/api/process-video-url', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: currentUser.user_id,
            video_url: url
        })
    })
    .then(res => res.json())
    .then(data => {
        status.style.display = 'none';
        
        if (data.success) {
            result.innerHTML = `
                <div style="background: #d1fae5; border: 1px solid #6ee7b7; padding: 15px; border-radius: 8px; color: #047857;">
                    <strong>✅ Başarılı!</strong><br>
                    Video: ${data.filename}<br>
                    ${data.new_words_found} yeni kelime bulundu
                </div>
            `;
            result.style.display = 'block';
            urlInput.value = ''; // Temizle
            setTimeout(() => loadWords(), 500);
            setTimeout(() => loadVideos(), 500);
        } else {
            result.innerHTML = `<div style="background: #fee2e2; border: 1px solid #fca5a5; padding: 15px; border-radius: 8px; color: #dc2626;">❌ Hata: ${data.error}</div>`;
            result.style.display = 'block';
        }
    })
    .catch(err => {
        status.style.display = 'none';
        result.innerHTML = '<div style="background: #fee2e2; padding: 15px; border-radius: 8px; color: #dc2626;">❌ Sunucu hatası</div>';
        result.style.display = 'block';
        console.error('Error:', err);
    })
    .finally(() => {
        btn.disabled = false;
    });
}

function loadWords() {
    if (!currentUser) return;

    return fetch(`/api/words?user_id=${currentUser.user_id}&known_only=${currentFilter === 'all' ? '' : currentFilter}`)
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Haritayı güncelle
            data.words.forEach(w => {
                userWordsMap.set(w.word.toLowerCase(), {id: w.id, known: w.known});
            });
            displayWords(data.words);
        }
    })
    .catch(err => console.error('Error:', err));
}

function displayWords(words) {
    const wordsList = document.getElementById('wordsList');
    
    if (words.length === 0) {
        wordsList.innerHTML = '<p>Kelime bulunamadı</p>';
        return;
    }

    // Filter only unknown words for flashcard display
    const unknownWords = words.filter(w => !w.known);
    const knownWords = words.filter(w => w.known);
    
    let html = '';
    
    // Display unknown words as flashcards
    if (unknownWords.length > 0) {
        html += '<div style="margin-bottom: 40px;"><h3 style="margin-bottom: 20px; font-size: 1.3em;">❌ Bilinmeyen Kelimeler</h3>';
        html += '<p style="margin-bottom: 15px; color: #6b7280; font-size: 0.9em;">Kartı çevirmek için tıkla, tanımı görmek için arka yüzü tıkla</p>';
        html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px;">';
        html += unknownWords.map(word => `
            <div class="word-card" data-word-id="${word.id}" style="cursor: pointer;">
                <div class="word-card-inner">
                    <div class="word-card-front">
                        <div class="word-text">${word.word}</div>
                        <div class="word-status">⬅️ Tıkla</div>
                    </div>
                    <div class="word-card-back">
                        <div class="word-definition" id="def-${word.id}">${word.definition || `<span class="fetch-def-btn" onclick="event.stopPropagation(); fetchDefinition(${word.id}, '${word.word}')" style="color: var(--primary); cursor: pointer; text-decoration: underline;">🔄 Çeviriyi Getir</span>`}</div>
                        <div class="word-pronunciation">${word.pronunciation ? `<em>(${word.pronunciation})</em>` : ''}</div>
                        <button class="btn btn-small btn-secondary" style="margin-top: 10px; font-size: 0.75em; background: white; color: #059669; border: 1px solid white;" data-word-id="${word.id}" data-mark="true">
                            ✅ Biliyorum
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
        html += '</div></div>';
    }
    
    // Display known words as simpler cards
    if (knownWords.length > 0) {
        html += '<div><h3 style="margin-bottom: 20px; font-size: 1.3em;">✅ Bilinen Kelimeler</h3>';
        html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px;">';
        html += knownWords.map(word => `
            <div style="background: rgba(16, 185, 129, 0.15); border: 2px solid var(--secondary); border-radius: 10px; padding: 15px; text-align: center; display: flex; flex-direction: column; justify-content: space-between; height: 120px;">
                <strong style="font-size: 1.1em;">${word.word}</strong>
                <button class="btn btn-small btn-danger" style="margin-top: 10px; font-size: 0.8em;" data-word-id="${word.id}" data-unmark="true">
                    ↩️ İşareti Kaldır
                </button>
            </div>
        `).join('');
        html += '</div></div>';
    }
    
    wordsList.innerHTML = html;
    
    // Add event listeners for flashcard flip
    document.querySelectorAll('.word-card').forEach(card => {
        card.addEventListener('click', function(e) {
            if (e.target.closest('[data-mark], [data-unmark]')) {
                return; // Don't flip if clicking button
            }
            e.stopPropagation();
            this.classList.toggle('flipped');
        });
    });
    
    // Add event listeners for mark buttons (on back of card)
    document.querySelectorAll('[data-mark]').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const wordId = this.dataset.wordId;
            toggleWordStatus(wordId, true); // Mark as known
        });
    });
    
    // Add event listeners for unmark buttons
    document.querySelectorAll('[data-unmark]').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const wordId = this.dataset.wordId;
            toggleWordStatus(wordId, false); // Mark as unknown
        });
    });
}

window.fetchDefinition = function(wordId, word) {
    const defElement = document.getElementById(`def-${wordId}`);
    defElement.innerHTML = '<em>Yükleniyor...</em>';
    
    fetch(`/api/words/${wordId}/definition?word=${encodeURIComponent(word)}`)
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            defElement.textContent = data.definition;
        } else {
            defElement.innerHTML = '<span style="color: red;">Bulunamadı</span>';
        }
    })
    .catch(err => {
        defElement.innerHTML = '<span style="color: red;">Hata</span>';
    });
}

function loadVideos() {
    const userIdParam = currentUser ? `?user_id=${currentUser.user_id}` : '';
    fetch('/api/videos' + userIdParam)
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            displayVideos(data.videos);
        }
    })
    .catch(err => console.error('Error loading videos:', err));
}

function displayVideos(videos) {
    const videosList = document.getElementById('videosList');
    
    if (!videos || videos.length === 0) {
        videosList.innerHTML = '<p>Henüz işlenmiş video yok.</p>';
        return;
    }

    videosList.innerHTML = videos.map((video, index) => `
        <div class="video-item" style="border: 1px solid #e5e7eb; padding: 15px; margin-bottom: 10px; border-radius: 8px; background: white;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div style="flex: 1;">
                    <strong>${video.title || video.filename || 'Video'}</strong><br>
                    ${video.description ? `<small style="color: #6b7280;">${video.description}</small><br>` : ''}
                    <small style="color: #9ca3af;">${new Date(video.processed_date || video.added_date).toLocaleString()} - ${video.word_count || 0} kelime</small>
                    ${renderLevelStats(video.level_stats)}
                </div>
                <div style="display: flex; gap: 5px;">
                    <button onclick="toggleTranscript('transcript-${index}')" class="btn btn-small btn-secondary">📝 Transkript</button>
                    <button onclick="deleteVideo(${video.id})" class="btn btn-small btn-danger">🗑️ Sil</button>
                </div>
            </div>
            <div id="transcript-${index}" style="display: none; margin-top: 15px; padding: 10px; background: #f9fafb; border-radius: 4px; font-size: 0.9em; line-height: 1.5; max-height: 300px; overflow-y: auto; border: 1px solid #e5e7eb;">
                ${video.transcript ? renderInteractiveTranscript(video.transcript) : '<em>Transkript mevcut değil.</em>'}
            </div>
        </div>
    `).join('');
}

function renderLevelStats(stats) {
    if (!stats || Object.keys(stats).length === 0) return '';
    
    let html = '<div style="margin-top: 8px;">';
    
    // Simple bar chart
    html += '<div style="display: flex; height: 6px; width: 100%; background: #f3f4f6; border-radius: 3px; overflow: hidden; margin-bottom: 5px;">';
    
    const total = Object.values(stats).reduce((a, b) => a + b, 0);
    const colors = ['#4ade80', '#60a5fa', '#f472b6', '#fbbf24', '#a78bfa', '#f87171'];
    let i = 0;
    
    // Sort keys to ensure Level 1, Level 2 order
    const sortedKeys = Object.keys(stats).sort((a, b) => {
        const numA = parseInt(a.match(/\d+/) || 0);
        const numB = parseInt(b.match(/\d+/) || 0);
        return numA - numB;
    });
    
    for (const key of sortedKeys) {
        const count = stats[key];
        const pct = (count / total) * 100;
        const color = colors[i % colors.length];
        html += `<div style="width: ${pct}%; background: ${color};" title="${key}: ${count}"></div>`;
        i++;
    }
    html += '</div>';
    
    // Text details
    html += '<div style="display: flex; flex-wrap: wrap; gap: 8px; font-size: 0.75em; color: #6b7280;">';
    
    sortedKeys.forEach((key, idx) => {
        if (idx < 6) { // Show first 6 levels explicitly
             // Extract "Level 1" from "Level 1: word - word"
             const shortName = key.split(':')[0].replace('Level ', 'L');
             html += `<span>${shortName}: <b>${stats[key]}</b></span>`;
        }
    });
    
    html += '</div></div>';
    return html;
}

window.toggleTranscript = function(id) {
    const el = document.getElementById(id);
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

window.deleteVideo = function(videoId) {
    if (!confirm('Bu videoyu ve analiz verilerini silmek istediğinize emin misiniz?')) return;
    
    fetch(`/api/videos/${videoId}`, {
        method: 'DELETE'
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            loadVideos();
        } else {
            alert('Silme işlemi başarısız');
        }
    })
    .catch(err => console.error('Error:', err));
}

function renderInteractiveTranscript(text) {
    if (!text) return '';
    // Metni kelimelere ve ayırıcılara böl (harfler ve kesme işareti olanları kelime say)
    const parts = text.split(/([a-zA-Z']+(?:-[a-zA-Z']+)?)/);
    
    return parts.map(part => {
        const lower = part.toLowerCase();
        if (userWordsMap.has(lower)) {
            const info = userWordsMap.get(lower);
            const color = info.known ? '#059669' : '#dc2626';
            const bg = info.known ? '#d1fae5' : '#fee2e2';
            return `<span class="interactive-word" 
                          data-word="${lower}"
                          style="cursor: pointer; background-color: ${bg}; color: ${color}; padding: 0 2px; border-radius: 2px; font-weight: 500;"
                          onclick="handleTranscriptWordClick('${lower}')"
                          title="${info.known ? 'Bilinen' : 'Bilinmeyen'} - Değiştirmek için tıkla">
                          ${escapeHtml(part)}
                    </span>`;
        } else {
            return escapeHtml(part);
        }
    }).join('');
}

window.handleTranscriptWordClick = function(word) {
    const info = userWordsMap.get(word);
    if (info) {
        toggleWordStatus(info.id, !info.known);
    }
}

function updateTranscriptHighlights() {
    document.querySelectorAll('.interactive-word').forEach(el => {
        const word = el.dataset.word;
        if (userWordsMap.has(word)) {
            const info = userWordsMap.get(word);
            const color = info.known ? '#059669' : '#dc2626';
            const bg = info.known ? '#d1fae5' : '#fee2e2';
            el.style.backgroundColor = bg;
            el.style.color = color;
            el.title = (info.known ? 'Bilinen' : 'Bilinmeyen') + ' - Değiştirmek için tıkla';
        }
    });
}

function filterKnown(filter) {
    currentFilter = filter;
    
    document.querySelectorAll('.controls .btn').forEach(btn => {
        btn.classList.remove('active-filter');
    });
    event.target.classList.add('active-filter');
    
    loadWords();
}

function toggleWordStatus(wordId, known) {
    if (!currentUser || !currentUser.user_id) {
        alert('Lütfen önce giriş yapın!');
        if (typeof showLoginSection === 'function') {
            showLoginSection();
        }
        return;
    }
    
    fetch(`/api/words/${wordId}/mark`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: currentUser.user_id,
            known: known
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Haritayı manuel güncelle (hızlı tepki için)
            for (let [word, info] of userWordsMap.entries()) {
                if (info.id === wordId) {
                    userWordsMap.set(word, {id: wordId, known: known});
                    break;
                }
            }
            
            loadWords().then(() => {
                updateTranscriptHighlights();
                loadStats();
            });
        }
    })
    .catch(err => console.error('Error:', err));
}

function loadStats() {
    if (!currentUser) return;

    fetch(`/api/stats?user_id=${currentUser.user_id}`)
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            const stats = data.stats;
            const percentage = stats.percentage || 0;
            
            const statsDiv = document.getElementById('statsContent');
            statsDiv.innerHTML = `
                <div style="padding: 20px; background: #f3f4f6; border-radius: 8px;">
                    <div style="margin-bottom: 15px;">
                        <strong>Toplam Kelime:</strong> ${stats.total}
                    </div>
                    <div style="margin-bottom: 15px;">
                        <strong>Bilinen:</strong> ${stats.known} (${percentage}%)
                    </div>
                    <div style="margin-bottom: 15px;">
                        <strong>Bilinmeyen:</strong> ${stats.unknown} (${100 - percentage}%)
                    </div>
                    <div style="background: #e5e7eb; border-radius: 8px; height: 20px; overflow: hidden;">
                        <div style="background: linear-gradient(90deg, #10b981, #059669); height: 100%; width: ${percentage}%; transition: width 0.3s;"></div>
                    </div>
                </div>
            `;
            
            // Kelime haritasını güncelle
            loadWordMap(stats);
        }
    })
    .catch(err => console.error('Error:', err));
}

function loadWordMap(stats) {
    if (!currentUser) return;

    // İstatistik kartlarını render et
    const wordStats = document.getElementById('wordStats');
    const percentage = stats.percentage || 0;
    
    if (wordStats) {
    wordStats.innerHTML = `
        <div class="stat-box">
            <div class="stat-box-label">📚 Toplam</div>
            <div class="stat-box-number">${stats.total}</div>
        </div>
        <div class="stat-box known">
            <div class="stat-box-label">✅ Bilinen</div>
            <div class="stat-box-number">${stats.known}</div>
            <div class="stat-box-percent">${percentage}%</div>
        </div>
        <div class="stat-box unknown">
            <div class="stat-box-label">❌ Bilinmeyen</div>
            <div class="stat-box-number">${stats.unknown}</div>
            <div class="stat-box-percent">${100 - percentage}%</div>
        </div>
    `;
    }

    // Level Sistemi Entegrasyonu
    const categoryMap = document.getElementById('wordCategoryMap');
    if (!categoryMap) return;

    fetch(`/api/packages?user_id=${currentUser.user_id}`)
    .then(res => res.json())
    .then(data => {
        if (data.success && data.packages) {
            renderLevelMap(data.packages);
        }
    })
    .catch(err => {
        console.error('Level map error:', err);
        categoryMap.innerHTML = '<div style="color: red; text-align: center; padding: 20px;">Seviyeler yüklenirken bir hata oluştu.</div>';
    });
}

function renderLevelMap(packages) {
    const categoryMap = document.getElementById('wordCategoryMap');
    if (!categoryMap) return;

    let html = '<div class="levels-grid" style="display: grid; gap: 20px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));">';

    packages.forEach(pkg => {
        const progress = pkg.progress_percentage || 0;
        // Renk skalası: Kırmızı -> Sarı -> Yeşil
        let statusColor = '#ef4444'; // Kırmızı
        if (progress > 30) statusColor = '#f59e0b'; // Sarı
        if (progress > 70) statusColor = '#10b981'; // Yeşil
        
        html += `
            <div class="level-card" onclick="loadLevelWords(${pkg.id}, '${escapeHtml(pkg.package_name)}')" style="
                background: white; 
                border: 1px solid #e5e7eb; 
                border-radius: 12px; 
                padding: 20px; 
                cursor: pointer; 
                transition: all 0.2s ease;
                position: relative;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            " onmouseover="this.style.transform='translateY(-3px)'; this.style.boxShadow='0 10px 15px -3px rgba(0, 0, 0, 0.1)'" onmouseout="this.style.transform='none'; this.style.boxShadow='0 2px 4px rgba(0,0,0,0.05)'">
                
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px;">
                    <div>
                        <h3 style="margin: 0; font-size: 1.1em; color: #1f2937; font-weight: 600;">${pkg.package_name}</h3>
                        <div style="font-size: 0.85em; color: #6b7280; margin-top: 5px;">
                            ${pkg.min_frequency} - ${pkg.max_frequency} Frekans Aralığı
                        </div>
                    </div>
                    <div style="background: ${statusColor}15; color: ${statusColor}; padding: 4px 10px; border-radius: 20px; font-size: 0.85em; font-weight: 700;">
                        %${progress}
                    </div>
                </div>
                
                <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: #4b5563; margin-bottom: 8px;">
                    <span>İlerleme</span>
                    <span>${pkg.known_words} / ${pkg.word_count}</span>
                </div>

                <div style="background: #f3f4f6; height: 8px; border-radius: 4px; overflow: hidden;">
                    <div style="width: ${progress}%; background: ${statusColor}; height: 100%; transition: width 0.5s ease-out;"></div>
                </div>
            </div>
        `;
    });

    html += '</div>';
    
    // Container for details
    html += '<div id="levelWordsContainer" style="margin-top: 30px; display: none;"></div>';

    categoryMap.innerHTML = html;

    // Restore open package if exists (sayfa yenilendiğinde açık kalması için)
    if (currentOpenPackageId) {
        const pkg = packages.find(p => p.id === currentOpenPackageId);
        if (pkg) {
            loadLevelWords(currentOpenPackageId, pkg.package_name);
        } else {
            currentOpenPackageId = null;
        }
    }
}

function loadLevelWords(packageId, packageName) {
    currentOpenPackageId = packageId;
    const container = document.getElementById('levelWordsContainer');
    if (!container) return;
    
    container.style.display = 'block';
    container.innerHTML = `
        <div style="text-align: center; padding: 40px; background: white; border-radius: 12px; border: 1px solid #e5e7eb;">
            <div style="display: inline-block; width: 30px; height: 30px; border: 3px solid #e5e7eb; border-top-color: #3b82f6; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 10px;"></div>
            <div>⏳ ${packageName} kelimeleri yükleniyor...</div>
            <style>@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>
        </div>
    `;
    
    // Scroll slightly to show the container
    setTimeout(() => {
        container.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);

    fetch(`/api/packages/${packageId}/words?user_id=${currentUser.user_id}`)
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            displayLevelWords(data.words, packageName);
        }
    })
    .catch(err => {
        console.error('Error loading level words:', err);
        container.innerHTML = '<div style="color: red; text-align: center; padding: 20px;">Kelimeler yüklenirken hata oluştu.</div>';
    });
}

function closeLevelWords() {
    currentOpenPackageId = null;
    const container = document.getElementById('levelWordsContainer');
    if (container) {
        container.style.display = 'none';
        container.innerHTML = '';
    }
    // Scroll back to top of levels
    const categoryMap = document.getElementById('wordCategoryMap');
    if (categoryMap) {
        categoryMap.scrollIntoView({ behavior: 'smooth' });
    }
}

function displayLevelWords(words, packageName) {
    const container = document.getElementById('levelWordsContainer');
    if (!container) return;
    
    const knownWords = words.filter(w => w.known);
    const unknownWords = words.filter(w => !w.known);
    
    // Count words with/without definitions
    const wordsWithDef = words.filter(w => w.definition && w.definition.trim()).length;
    const wordsWithoutDef = words.length - wordsWithDef;
    
    let html = `
        <div style="background: white; border-radius: 12px; padding: 25px; border: 1px solid #e5e7eb; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; border-bottom: 1px solid #f3f4f6; padding-bottom: 15px; flex-wrap: wrap; gap: 15px;">
                <div>
                    <h3 style="margin: 0; color: #111827; font-size: 1.5em;">📂 ${packageName}</h3>
                    <div style="color: #6b7280; font-size: 0.9em; margin-top: 5px;">Toplam ${words.length} kelime | ${wordsWithDef} çevrilmiş</div>
                </div>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    ${wordsWithoutDef > 0 ? `
                    <button data-translate-package="${currentOpenPackageId}" onclick="translatePackageWords(${currentOpenPackageId})" class="btn btn-secondary" style="display: flex; align-items: center; gap: 5px;">
                        <span>🤖</span> ${wordsWithoutDef} Kelimeyi Çevir
                    </button>
                    ` : ''}
                    <button onclick="startPackageFlashcards(${currentOpenPackageId}, '${escapeHtml(packageName)}')" class="btn btn-primary" style="display: flex; align-items: center; gap: 5px;">
                        <span>🧠</span> Kartlarla Çalış
                    </button>
                    <button onclick="closeLevelWords()" class="btn btn-secondary" style="display: flex; align-items: center; gap: 5px;">
                        <span>✕</span> Kapat
                    </button>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 30px;">
    `;
    
    // Unknown Column - Show definitions
    html += `
        <div>
            <h4 style="color: #dc2626; margin: 0 0 15px; display: flex; align-items: center; gap: 8px; font-size: 1.1em;">
                <span>❌</span> Öğrenilecekler (${unknownWords.length})
            </h4>
            <div class="word-bubble-container" style="background: #fef2f2; padding: 15px; border-radius: 8px; border: 1px solid #fee2e2; max-height: 500px; overflow-y: auto;">
                ${unknownWords.length > 0 ? unknownWords.map(w => `
                    <div class="word-item-with-def" onclick="toggleWordStatus(${w.id}, true)" style="
                        display: flex; 
                        justify-content: space-between; 
                        align-items: center; 
                        padding: 10px 15px; 
                        margin-bottom: 8px; 
                        background: white; 
                        border-radius: 8px; 
                        border: 1px solid #fecaca;
                        cursor: pointer;
                        transition: all 0.2s;
                    " onmouseover="this.style.background='#fef2f2'; this.style.transform='translateX(5px)'" onmouseout="this.style.background='white'; this.style.transform='none'">
                        <div>
                            <div style="font-weight: 600; color: #1f2937; font-size: 1em;">${w.word}</div>
                            <div style="font-size: 0.85em; color: ${w.definition ? '#059669' : '#9ca3af'}; margin-top: 2px;">
                                ${w.definition ? '→ ' + w.definition : '(çeviri bekleniyor)'}
                            </div>
                        </div>
                        <div style="color: #9ca3af; font-size: 0.75em; text-align: right;">
                            <div>f: ${w.frequency || 0}</div>
                            <div style="color: #10b981; margin-top: 2px;">✓ öğren</div>
                        </div>
                    </div>
                `).join('') : '<div style="color: #991b1b; font-style: italic; text-align: center; padding: 20px;">Bu seviyedeki tüm kelimeleri öğrendiniz! 🎉</div>'}
            </div>
        </div>
    `;
    
    // Known Column - Show definitions
    html += `
        <div>
            <h4 style="color: #059669; margin: 0 0 15px; display: flex; align-items: center; gap: 8px; font-size: 1.1em;">
                <span>✅</span> Bilinenler (${knownWords.length})
            </h4>
            <div class="word-bubble-container" style="background: #ecfdf5; padding: 15px; border-radius: 8px; border: 1px solid #d1fae5; max-height: 500px; overflow-y: auto;">
                ${knownWords.length > 0 ? knownWords.map(w => `
                    <div class="word-item-with-def" onclick="toggleWordStatus(${w.id}, false)" style="
                        display: flex; 
                        justify-content: space-between; 
                        align-items: center; 
                        padding: 10px 15px; 
                        margin-bottom: 8px; 
                        background: white; 
                        border-radius: 8px; 
                        border: 1px solid #a7f3d0;
                        cursor: pointer;
                        transition: all 0.2s;
                    " onmouseover="this.style.background='#ecfdf5'; this.style.transform='translateX(5px)'" onmouseout="this.style.background='white'; this.style.transform='none'">
                        <div>
                            <div style="font-weight: 600; color: #1f2937; font-size: 1em;">${w.word}</div>
                            <div style="font-size: 0.85em; color: ${w.definition ? '#059669' : '#9ca3af'}; margin-top: 2px;">
                                ${w.definition ? '→ ' + w.definition : '(çeviri bekleniyor)'}
                            </div>
                        </div>
                        <div style="color: #9ca3af; font-size: 0.75em; text-align: right;">
                            <div>f: ${w.frequency || 0}</div>
                            <div style="color: #ef4444; margin-top: 2px;">✗ kaldır</div>
                        </div>
                    </div>
                `).join('') : '<div style="color: #065f46; font-style: italic; text-align: center; padding: 20px;">Henüz bilinen kelime yok.</div>'}
            </div>
        </div>
    `;
    
    html += `
            </div>
        </div>
    `;
    
    container.innerHTML = html;
}

function loadUserProfile() {
    if (!currentUser) return;

    const userInfo = document.getElementById('userInfo');
    userInfo.innerHTML = `
        <strong>Kullanıcı Adı:</strong> ${currentUser.username}<br>
        <strong>Kullanıcı ID:</strong> ${currentUser.user_id}
    `;

    loadStats();
}

// ===== DATA MANAGEMENT =====

function downloadBackup() {
    window.location.href = '/api/backup';
}

function restoreBackup(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!confirm('⚠️ DİKKAT: Mevcut verilerinizin üzerine yazılacak ve şu anki verileriniz silinecek. Devam etmek istiyor musunuz?')) {
        event.target.value = '';
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    fetch('/api/restore', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            alert('✅ ' + data.message);
            location.reload();
        } else {
            alert('❌ Hata: ' + data.error);
        }
    })
    .catch(err => console.error('Error:', err));
    
    event.target.value = '';
}

// ===== UTILITY FUNCTIONS =====

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function showNotification(message) {
    console.log('Notification:', message);
}

// ===== FRIENDS TRANSCRIPTS LOADER =====

function loadFriendsTranscripts() {
    const statusDiv = document.getElementById('friendsLoadStatus');
    const btn = document.getElementById('loadFriendsBtn');
    const seasonSelect = document.getElementById('friendsSeasonSelect');
    const selectedSeason = seasonSelect ? seasonSelect.value : 'all';
    
    statusDiv.style.display = 'block';
    btn.disabled = true;
    
    console.log(`🎬 Friends transkriptleri yükleniyor (${selectedSeason === 'all' ? 'Tüm Sezonlar' : 'Sezon ' + selectedSeason})...`);
    
    fetch('/api/friends/load', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: currentUser?.user_id,
            season: selectedSeason
        })
    })
    .then(res => res.json())
    .then(data => {
        statusDiv.style.display = 'none';
        btn.disabled = false;
        
        if (data.success) {
            console.log('✅ ' + data.message);
            alert(`✅ ${data.message}\n\n${data.count} bölüm eklendi!`);
            setTimeout(() => loadVideos(), 500);
        } else {
            console.error('❌ Hata:', data.error);
            alert('❌ Friends transkriptleri yüklenirken hata: ' + data.error);
        }
    })
    .catch(err => {
        statusDiv.style.display = 'none';
        btn.disabled = false;
        console.error('❌ Yükleme hatası:', err);
        alert('❌ Yükleme sırasında hata oluştu: ' + err.message);
    });
}

function processDiziboxVideo() {
    const urlInput = document.getElementById('diziboxUrl');
    const url = urlInput?.value.trim();
    
    if (!url) {
        alert('Lütfen bir Dizibox linki yapıştırın');
        return;
    }

    if (!currentUser || !currentUser.user_id) {
        alert('Lütfen önce giriş yapın');
        return;
    }
    
    const statusDiv = document.getElementById('diziboxStatus');
    const resultDiv = document.getElementById('diziboxResult');
    const statusText = document.getElementById('diziboxStatusText');
    const btn = document.getElementById('processDiziboxBtn');
    
    statusDiv.style.display = 'block';
    resultDiv.style.display = 'none';
    statusText.textContent = '📥 Video indiriliyor...';
    btn.disabled = true;
    
    fetch('/api/process-video-url', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user_id: currentUser?.user_id,
            video_url: url
        })
    })
    .then(res => res.json())
    .then(data => {
        statusDiv.style.display = 'none';
        btn.disabled = false;
        
        if (data.success) {
            const resultHtml = `
                <div style="background: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 5px; color: #155724;">
                    <h3>✅ Dizibox Video Başarıyla İşlendi!</h3>
                    <p><strong>Dosya:</strong> ${data.filename}</p>
                    <p><strong>Yeni Kelimeler:</strong> ${data.new_words_found}</p>
                    <p><strong>Toplam Kelime:</strong> ${data.total_words}</p>
                    <p><strong>Transkript Önizlemesi:</strong></p>
                    <pre style="max-height: 200px; overflow-y: auto; background: #fff; padding: 10px; border-radius: 3px;">${data.transcript_preview}</pre>
                </div>
            `;
            resultDiv.innerHTML = resultHtml;
            resultDiv.style.display = 'block';
            urlInput.value = '';
            setTimeout(() => loadVideos(), 500);
        } else {
            const errorHtml = `
                <div style="background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px; color: #721c24;">
                    <h3>❌ İşlem Başarısız</h3>
                    <p><strong>Hata:</strong> ${data.error}</p>
                    <p style="font-size: 0.9em; margin-top: 10px;">
                        💡 İpucu: Linkinin doğru olduğundan emin olun. yt-dlp bazı siteleri desteklemeyebilir.
                    </p>
                </div>
            `;
            resultDiv.innerHTML = errorHtml;
            resultDiv.style.display = 'block';
        }
    })
    .catch(err => {
        statusDiv.style.display = 'none';
        btn.disabled = false;
        const errorHtml = `
            <div style="background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px; color: #721c24;">
                <h3>❌ Hata Oluştu</h3>
                <p>${err.message}</p>
            </div>
        `;
        resultDiv.innerHTML = errorHtml;
        resultDiv.style.display = 'block';
        console.error('❌ Dizibox işleminde hata:', err);
    });
}

// ===== VOCABULARY LEVEL TEST =====

let vocabTestState = null;

function startVocabTest() {
    if (!requireLogin(() => startVocabTest(), 'Kelime seviye testi için giriş yapmanız gerekiyor.')) {
        return;
    }

    fetch('/api/vocab-test/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: currentUser.user_id })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            vocabTestState = data.state;
            showVocabTestModal(data.current_word, data.total_words);
        } else {
            alert('Test başlatılamadı: ' + data.error);
        }
    })
    .catch(err => console.error('Error:', err));
}

function showVocabTestModal(word, total) {
    let modal = document.getElementById('vocabTestModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'vocabTestModal';
        modal.style.cssText = `position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 10000; display: flex; justify-content: center; align-items: center;`;
        document.body.appendChild(modal);
    }

    modal.innerHTML = `
        <div style="background: white; width: 90%; max-width: 500px; padding: 30px; border-radius: 15px; text-align: center; position: relative; box-shadow: 0 20px 50px rgba(0,0,0,0.3);">
            <button onclick="document.getElementById('vocabTestModal').remove()" style="position: absolute; right: 15px; top: 15px; border: none; background: none; font-size: 1.5em; cursor: pointer; color: #666;">✕</button>
            <h2 style="margin-bottom: 10px; color: #3b82f6;">📊 Kelime Seviye Testi</h2>
            <p style="color: #6b7280; margin-bottom: 30px;">Bu kelimenin anlamını biliyor musun?</p>
            
            <div style="background: #f3f4f6; padding: 30px; border-radius: 10px; margin-bottom: 30px;">
                <div style="font-size: 2.5em; font-weight: bold; color: #1f2937;">${word.word}</div>
                ${word.pronunciation ? `<div style="color: #6b7280; margin-top: 5px;">${word.pronunciation}</div>` : ''}
            </div>

            <div style="display: flex; gap: 15px; justify-content: center;">
                <button onclick="submitVocabAnswer(false)" class="btn btn-danger" style="flex: 1; padding: 15px; font-size: 1.1em;">❌ Bilmiyorum</button>
                <button onclick="submitVocabAnswer(true)" class="btn btn-success" style="flex: 1; padding: 15px; font-size: 1.1em;">✅ Biliyorum</button>
            </div>
            <div style="margin-top: 20px; font-size: 0.8em; color: #9ca3af;">Veritabanındaki ${total} kelime üzerinden test ediliyor</div>
        </div>
    `;
}

window.submitVocabAnswer = function(answer) {
    fetch('/api/vocab-test/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            answer: answer,
            state: vocabTestState
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            if (data.status === 'continue') {
                vocabTestState = data.state;
                showVocabTestModal(data.current_word, data.state.end - data.state.start + 1); // Show remaining range approx
            } else if (data.status === 'finished') {
                const result = data.result;
                const modal = document.getElementById('vocabTestModal');
                modal.innerHTML = `
                    <div style="background: white; width: 90%; max-width: 500px; padding: 40px; border-radius: 15px; text-align: center;">
                        <h2 style="margin-bottom: 20px; color: #10b981;">🎉 Test Tamamlandı!</h2>
                        <div style="font-size: 4em; font-weight: bold; color: #3b82f6; margin: 20px 0;">${result.estimated_vocab}</div>
                        <p style="font-size: 1.2em; color: #4b5563;">Tahmini Kelime Hazineniz</p>
                        <p style="color: #6b7280; margin-top: 10px;">Veritabanındaki en sık kullanılan kelimelerin <strong>%${result.percentage}</strong> kadarını biliyorsunuz.</p>
                        <button onclick="document.getElementById('vocabTestModal').remove()" class="btn btn-primary" style="margin-top: 30px; width: 100%;">Harika!</button>
                    </div>
                `;
            }
        }
    });
}

// ===== FLASHCARD LEARNING SYSTEM =====

// Open flashcard study modal with options
window.openFlashcardModal = function() {
    if (!requireLogin(() => openFlashcardModal(), 'Flashcard çalışması için giriş yapmanız gerekiyor.')) {
        return;
    }

    // Create modal
    let modal = document.getElementById('flashcardStudyModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'flashcardStudyModal';
        modal.style.cssText = `position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 10000; display: flex; justify-content: center; align-items: center;`;
        document.body.appendChild(modal);
    }

    // Load options
    fetch(`/api/flashcards/options?user_id=${currentUser.user_id}`)
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showFlashcardOptionsModal(modal, data);
        }
    })
    .catch(err => {
        console.error('Error loading flashcard options:', err);
        modal.innerHTML = '<div style="background: white; padding: 30px; border-radius: 15px; text-align: center;"><h3>Hata oluştu</h3><button onclick="document.getElementById(\'flashcardStudyModal\').remove()" class="btn btn-primary">Kapat</button></div>';
    });
}

function showFlashcardOptionsModal(modal, data) {
    const { options, user_stats } = data;
    
    let html = `
        <div style="background: white; width: 95%; max-width: 700px; max-height: 90vh; overflow-y: auto; padding: 30px; border-radius: 15px; position: relative;">
            <button onclick="closeFlashcardStudyModal()" style="position: absolute; right: 15px; top: 15px; border: none; background: none; font-size: 1.5em; cursor: pointer; color: #9ca3af;">✕</button>
            
            <h2 style="margin-bottom: 10px; color: #1f2937;">🧠 Kartla Çalış</h2>
            <p style="color: #6b7280; margin-bottom: 25px;">Çalışmak istediğiniz kelime grubunu seçin</p>
            
            <div style="margin-bottom: 25px;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold;">${user_stats.total}</div>
                        <div style="font-size: 0.85em; opacity: 0.9;">Toplam Kelime</div>
                    </div>
                    <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 15px; border-radius: 10px; text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold;">${user_stats.unknown}</div>
                        <div style="font-size: 0.85em; opacity: 0.9;">Bilinmeyen</div>
                    </div>
                    <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 15px; border-radius: 10px; text-align: center;">
                        <div style="font-size: 1.8em; font-weight: bold;">${user_stats.known}</div>
                        <div style="font-size: 0.85em; opacity: 0.9;">Bilinen</div>
                    </div>
                </div>
            </div>
            
            <div style="display: grid; gap: 15px;">
                <!-- Quick Options -->
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;">
                    <button onclick="startFlashcardSession('all')" class="btn btn-primary" style="padding: 15px; display: flex; flex-direction: column; align-items: center; gap: 5px;">
                        <span style="font-size: 1.3em;">📚</span>
                        <span>Tüm Bilinmeyenler</span>
                        <small style="opacity: 0.8;">${options.all_words?.unknown_words || 0} kelime</small>
                    </button>
                    <button onclick="startFlashcardSession('problem')" class="btn btn-warning" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; padding: 15px; display: flex; flex-direction: column; align-items: center; gap: 5px;">
                        <span style="font-size: 1.3em;">⚠️</span>
                        <span>Zorlandıklarım</span>
                        <small style="opacity: 0.8;">${options.problem_words?.unknown_words || 0} kelime</small>
                    </button>
                    <button onclick="startFlashcardSession('random')" class="btn btn-secondary" style="padding: 15px; display: flex; flex-direction: column; align-items: center; gap: 5px;">
                        <span style="font-size: 1.3em;">🎲</span>
                        <span>Rastgele 50</span>
                        <small style="opacity: 0.8;">${options.random?.unknown_words || 0} kelime</small>
                    </button>
                    <button onclick="showLevelSelector()" class="btn btn-secondary" style="padding: 15px; display: flex; flex-direction: column; align-items: center; gap: 5px;">
                        <span style="font-size: 1.3em;">📊</span>
                        <span>Seviyeye Göre</span>
                        <small style="opacity: 0.8;">${options.levels?.length || 0} seviye</small>
                    </button>
                </div>
                
                <!-- Levels Accordion -->
                <div id="levelSelector" style="display: none; margin-top: 15px;">
                    <h4 style="margin-bottom: 10px; color: #374151;">Öğrenme Seviyeleri</h4>
                    <div style="max-height: 200px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px;">
                        ${options.levels?.map(level => `
                            <div onclick="startFlashcardSession('level', ${level.id}, '${escapeHtml(level.name)}')" style="padding: 12px; border-bottom: 1px solid #e5e7eb; cursor: pointer; display: flex; justify-content: space-between; align-items: center; hover: background: #f3f4f6;">
                                <div>
                                    <div style="font-weight: 500;">${level.name}</div>
                                    <div style="font-size: 0.8em; color: #6b7280;">${level.total_words} kelime</div>
                                </div>
                                <div style="text-align: right;">
                                    <span style="background: ${level.unknown_words > 0 ? '#f59e0b' : '#10b981'}; color: white; padding: 3px 8px; border-radius: 10px; font-size: 0.8em;">${level.unknown_words} bilinmeyen</span>
                                </div>
                            </div>
                        `).join('') || '<div style="padding: 15px; text-align: center; color: #6b7280;">Seviye bulunamadı</div>'}
                    </div>
                </div>
                
                <!-- Videos Accordion -->
                <div id="videoSelector" style="display: none; margin-top: 15px;">
                    <h4 style="margin-bottom: 10px; color: #374151;">Videolardaki Kelimeler</h4>
                    <div style="max-height: 200px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px;">
                        ${options.videos?.map(video => `
                            <div onclick="startFlashcardSession('video', ${video.id}, '${escapeHtml(video.title)}')" style="padding: 12px; border-bottom: 1px solid #e5e7eb; cursor: pointer; display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <div style="font-weight: 500; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${video.title}</div>
                                </div>
                                <div style="text-align: right;">
                                    <span style="background: ${video.unknown_words > 0 ? '#f59e0b' : '#10b981'}; color: white; padding: 3px 8px; border-radius: 10px; font-size: 0.8em;">${video.unknown_words} bilinmeyen</span>
                                </div>
                            </div>
                        `).join('') || '<div style="padding: 15px; text-align: center; color: #6b7280;">Video bulunamadı</div>'}
                    </div>
                </div>
            </div>
            
            <div style="margin-top: 20px; padding: 15px; background: #f3f4f6; border-radius: 8px; font-size: 0.85em; color: #6b7280;">
                <strong>💡 Klavye Kısayolları:</strong><br>
                ← / Bilmiyorum • → / Biliyorum • ↑ / Kartı Çevir • ↓ / Atla • Esc / Kapat
            </div>
        </div>
    `;
    
    modal.innerHTML = html;
}

window.showLevelSelector = function() {
    const selector = document.getElementById('levelSelector');
    const videoSelector = document.getElementById('videoSelector');
    if (selector) {
        selector.style.display = selector.style.display === 'none' ? 'block' : 'none';
    }
    if (videoSelector) videoSelector.style.display = 'none';
}

window.showVideoSelector = function() {
    const selector = document.getElementById('videoSelector');
    const levelSelector = document.getElementById('levelSelector');
    if (selector) {
        selector.style.display = selector.style.display === 'none' ? 'block' : 'none';
    }
    if (levelSelector) levelSelector.style.display = 'none';
}

window.startFlashcardSession = function(type, targetId = null, targetName = null) {
    if (!requireLogin(() => startFlashcardSession(type, targetId, targetName), 'Flashcard çalışması için giriş yapmanız gerekiyor.')) {
        return;
    }

    fetch('/api/flashcards/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: currentUser.user_id,
            type: type,
            target_id: targetId
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            flashcardSessionId = data.session_id;
            flashcardCurrentWord = data.current_word;
            flashcardIsFlipped = false;
            
            closeFlashcardStudyModal();
            showFlashcardStudyModal(targetName || data.session_type, data.current_word, data.stats);
        } else {
            alert('Oturum başlatılamadı: ' + (data.message || data.error));
        }
    })
    .catch(err => {
        console.error('Error starting flashcard session:', err);
        alert('Oturum başlatılırken hata oluştu');
    });
}

function showFlashcardStudyModal(sessionName, word, stats) {
    let modal = document.getElementById('flashcardActiveModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'flashcardActiveModal';
        modal.style.cssText = `position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 10000; display: flex; justify-content: center; align-items: center;`;
        document.body.appendChild(modal);
        
        // Add keyboard event listener
        document.addEventListener('keydown', handleFlashcardKeyboard);
    }
    
    renderFlashcard(modal, sessionName, word, stats);
}

function renderFlashcard(modal, sessionName, word, stats) {
    const percentage = stats.percentage || 0;
    const progress = ((stats.total_cards - stats.remaining) / stats.total_cards * 100) || 0;
    
    // Determine card color based on attempts (red if struggled)
    const cardColor = word.attempts > 1 ? 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)' : 
                      word.attempts > 0 ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' :
                      'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)';
    
    modal.innerHTML = `
        <div style="background: white; width: 95%; max-width: 500px; padding: 25px; border-radius: 15px; position: relative; min-height: 450px; display: flex; flex-direction: column;">
            <!-- Header -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <div>
                    <span style="font-size: 0.9em; color: #6b7280;">${sessionName}</span>
                    <div style="font-size: 0.8em; color: #9ca3af;">${stats.correct_answers}/${stats.total_cards} doğru</div>
                </div>
                <button onclick="closeFlashcardStudyModal()" style="border: none; background: none; font-size: 1.3em; cursor: pointer; color: #9ca3af; padding: 5px;">✕</button>
            </div>
            
            <!-- Progress Bar -->
            <div style="background: #e5e7eb; height: 8px; border-radius: 4px; overflow: hidden; margin-bottom: 15px;">
                <div style="width: ${progress}%; background: ${percentage >= 70 ? '#10b981' : percentage >= 40 ? '#f59e0b' : '#3b82f6'}; height: 100%; transition: width 0.3s;"></div>
            </div>
            
            <!-- Flashcard -->
            <div id="flashcardCard" onclick="toggleFlashcardFlip()" style="flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; perspective: 1000px; cursor: pointer; min-height: 250px;">
                <div id="flashcardInner" style="position: relative; width: 100%; height: 220px; transition: transform 0.6s; transform-style: preserve-3d; ${flashcardIsFlipped ? 'transform: rotateY(180deg);' : ''}">
                    <!-- Front -->
                    <div style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; flex-direction: column; justify-content: center; align-items: center; border-radius: 12px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); background: ${cardColor}; color: white;">
                        <div style="font-size: 2.5em; font-weight: bold; text-align: center; word-break: break-word;">${word.word}</div>
                        <div style="margin-top: 15px; font-size: 0.85em; opacity: 0.9;">(Çevirmek için tıkla veya ↑)</div>
                        ${word.pronunciation ? `<div style="margin-top: 8px; font-style: italic; opacity: 0.8;">${word.pronunciation}</div>` : ''}
                    </div>
                    <!-- Back - Turkish Definition -->
                    <div style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; transform: rotateY(180deg); display: flex; flex-direction: column; justify-content: center; align-items: center; border-radius: 12px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white;">
                        <div style="font-size: 0.9em; opacity: 0.9; margin-bottom: 10px;">🇹🇷 Türkçe Anlamı</div>
                        <div style="font-size: 1.8em; font-weight: bold; text-align: center; line-height: 1.4;">${word.definition || '(Çeviri henüz eklenmemiş)'}</div>
                        <div style="margin-top: 15px; font-size: 0.85em; opacity: 0.8;">Frekans: ${word.frequency}</div>
                        ${word.attempts > 0 ? `<div style="margin-top: 5px; font-size: 0.8em; opacity: 0.9;">Bu kelimeye ${word.attempts} kez bakıldı</div>` : ''}
                    </div>
                </div>
            </div>
            
            <!-- Progress Circle -->
            <div style="display: flex; justify-content: center; margin: 15px 0;">
                <div style="position: relative; width: 60px; height: 60px;">
                    <svg width="60" height="60" style="transform: rotate(-90deg);">
                        <circle cx="30" cy="30" r="25" fill="none" stroke="#e5e7eb" stroke-width="5"/>
                        <circle cx="30" cy="30" r="25" fill="none" stroke="${percentage >= 70 ? '#10b981' : percentage >= 40 ? '#f59e0b' : '#3b82f6'}" stroke-width="5" 
                                stroke-dasharray="${157 * percentage / 100} 157" stroke-linecap="round"/>
                    </svg>
                    <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 0.9em; font-weight: bold; color: #374151;">${Math.round(percentage)}%</div>
                </div>
            </div>
            
            <!-- Buttons -->
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                <button onclick="skipFlashcard()" class="btn btn-secondary" style="padding: 12px;">⏭️ Atla (↓)</button>
                <button onclick="submitFlashcardAnswer(false)" class="btn btn-danger" style="padding: 12px;">❌ Bilmiyorum (←)</button>
                <button onclick="submitFlashcardAnswer(true)" class="btn btn-success" style="padding: 12px;">✅ Biliyorum (→)</button>
            </div>
            
            <!-- Stats Row -->
            <div style="display: flex; justify-content: center; gap: 20px; margin-top: 12px; font-size: 0.85em; color: #6b7280;">
                <span style="color: #ef4444;">❌ ${stats.incorrect_answers || 0}</span>
                <span style="color: #f59e0b;">⏭️ ${stats.skipped || 0}</span>
                <span style="color: #10b981;">✅ ${stats.correct_answers}</span>
            </div>
        </div>
    `;
}

window.toggleFlashcardFlip = function() {
    flashcardIsFlipped = !flashcardIsFlipped;
    const card = document.getElementById('flashcardInner');
    if (card) {
        card.style.transform = flashcardIsFlipped ? 'rotateY(180deg)' : 'rotateY(0)';
    }
}

function handleFlashcardKeyboard(e) {
    if (!flashcardSessionId || !flashcardCurrentWord) return;
    
    switch(e.key) {
        case 'ArrowUp':
        case ' ':
            e.preventDefault();
            toggleFlashcardFlip();
            break;
        case 'ArrowLeft':
            e.preventDefault();
            submitFlashcardAnswer(false);
            break;
        case 'ArrowRight':
            e.preventDefault();
            submitFlashcardAnswer(true);
            break;
        case 'ArrowDown':
            e.preventDefault();
            skipFlashcard();
            break;
        case 'Escape':
            e.preventDefault();
            closeFlashcardStudyModal();
            break;
    }
}

function submitFlashcardAnswer(isCorrect) {
    if (!flashcardSessionId || !flashcardCurrentWord) return;
    
    if (!currentUser || !currentUser.user_id) {
        alert('Lütfen önce giriş yapın!');
        if (typeof showLoginSection === 'function') {
            showLoginSection();
        }
        return;
    }
    
    fetch(`/api/flashcards/session/${flashcardSessionId}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: currentUser.user_id,
            word_id: flashcardCurrentWord.id,
            correct: isCorrect
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            if (data.completed) {
                // Show completion modal
                showFlashcardCompletion(data.stats);
            } else {
                flashcardCurrentWord = data.current_word;
                flashcardIsFlipped = false;
                
                const modal = document.getElementById('flashcardActiveModal');
                if (modal) {
                    renderFlashcard(modal, 'Kart Çalışması', data.current_word, data.session_stats);
                }
            }
        }
    })
    .catch(err => console.error('Error submitting answer:', err));
}

function skipFlashcard() {
    if (!flashcardSessionId || !flashcardCurrentWord) return;
    
    fetch(`/api/flashcards/session/${flashcardSessionId}/skip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: currentUser.user_id,
            word_id: flashcardCurrentWord.id
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            if (data.completed) {
                showFlashcardCompletion(data.stats);
            } else {
                flashcardCurrentWord = data.current_word;
                flashcardIsFlipped = false;
                
                const modal = document.getElementById('flashcardActiveModal');
                if (modal) {
                    renderFlashcard(modal, 'Kart Çalışması', data.current_word, data.stats);
                }
            }
        }
    })
    .catch(err => console.error('Error skipping card:', err));
}

function showFlashcardCompletion(stats) {
    closeFlashcardStudyModal();
    
    let modal = document.getElementById('flashcardCompletionModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'flashcardCompletionModal';
        modal.style.cssText = `position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 10000; display: flex; justify-content: center; align-items: center;`;
        document.body.appendChild(modal);
    }
    
    modal.innerHTML = `
        <div style="background: white; width: 90%; max-width: 450px; padding: 40px; border-radius: 15px; text-align: center;">
            <div style="font-size: 4em; margin-bottom: 15px;">🎉</div>
            <h2 style="margin-bottom: 10px; color: #10b981;">Tebrikler!</h2>
            <p style="color: #6b7280; margin-bottom: 25px;">Oturumu başarıyla tamamladınız!</p>
            
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 25px;">
                <div style="background: #f3f4f6; padding: 15px; border-radius: 10px;">
                    <div style="font-size: 2em; font-weight: bold; color: #3b82f6;">${stats.total_cards}</div>
                    <div style="font-size: 0.85em; color: #6b7280;">Toplam</div>
                </div>
                <div style="background: #d1fae5; padding: 15px; border-radius: 10px;">
                    <div style="font-size: 2em; font-weight: bold; color: #059669;">${stats.correct_answers}</div>
                    <div style="font-size: 0.85em; color: #6b7280;">Doğru</div>
                </div>
                <div style="background: #fee2e2; padding: 15px; border-radius: 10px;">
                    <div style="font-size: 2em; font-weight: bold; color: #dc2626;">${stats.incorrect_answers || 0}</div>
                    <div style="font-size: 0.85em; color: #6b7280;">Yanlış</div>
                </div>
                <div style="background: #fef3c7; padding: 15px; border-radius: 10px;">
                    <div style="font-size: 2em; font-weight: bold; color: #d97706;">${stats.percentage}%</div>
                    <div style="font-size: 0.85em; color: #6b7280;">Başarı</div>
                </div>
            </div>
            
            <button onclick="closeFlashcardCompletion()" class="btn btn-primary" style="width: 100%; padding: 15px;">Harika!</button>
        </div>
    `;
}

window.closeFlashcardCompletion = function() {
    const modal = document.getElementById('flashcardCompletionModal');
    if (modal) modal.remove();
    // Refresh the page to update stats
    loadStats();
}

window.closeFlashcardStudyModal = function() {
    const modal = document.getElementById('flashcardActiveModal');
    if (modal) {
        modal.remove();
        document.removeEventListener('keydown', handleFlashcardKeyboard);
    }
    flashcardSessionId = null;
    flashcardCurrentWord = null;
    flashcardIsFlipped = false;
}

window.closeFlashcardOptionsModal = function() {
    const modal = document.getElementById('flashcardStudyModal');
    if (modal) modal.remove();
}

// Legacy function for level-specific flashcards (now uses new system)
window.startPackageFlashcards = function(packageId, packageName) {
    startFlashcardSession('level', packageId, packageName);
}

// ===== CUSTOM SERIES FUNCTIONS =====

let selectedSeriesEmoji = '🎬';

// Open Add Series Modal
window.openAddSeriesModal = function() {
    const modal = document.getElementById('addSeriesModal');
    if (modal) {
        modal.style.display = 'flex';
        // Reset form
        document.getElementById('newSeriesName').value = '';
        document.getElementById('newSeriesUrl').value = '';
        document.getElementById('selectedEmoji').value = '🎬';
        selectedSeriesEmoji = '🎬';
        document.getElementById('addSeriesStatus').style.display = 'none';
        document.getElementById('addSeriesError').style.display = 'none';
        document.getElementById('addSeriesSuccess').style.display = 'none';
        document.getElementById('addSeriesBtn').disabled = false;
        
        // Reset emoji buttons
        document.querySelectorAll('.emoji-btn').forEach(btn => {
            btn.style.border = '2px solid #e5e7eb';
            btn.style.background = 'white';
        });
        const defaultBtn = document.querySelector('.emoji-btn[data-emoji="🎬"]');
        if (defaultBtn) {
            defaultBtn.style.border = '2px solid #6366f1';
            defaultBtn.style.background = '#eef2ff';
        }
    }
}

// Close Add Series Modal
window.closeAddSeriesModal = function() {
    const modal = document.getElementById('addSeriesModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Select Emoji
window.selectEmoji = function(emoji) {
    selectedSeriesEmoji = emoji;
    document.getElementById('selectedEmoji').value = emoji;
    
    // Update button styles
    document.querySelectorAll('.emoji-btn').forEach(btn => {
        if (btn.dataset.emoji === emoji) {
            btn.style.border = '2px solid #6366f1';
            btn.style.background = '#eef2ff';
        } else {
            btn.style.border = '2px solid #e5e7eb';
            btn.style.background = 'white';
        }
    });
}

// Add New Series
window.addNewSeries = async function() {
    const name = document.getElementById('newSeriesName').value.trim();
    const url = document.getElementById('newSeriesUrl').value.trim();
    const icon = selectedSeriesEmoji || '🎬';
    
    if (!name) {
        document.getElementById('addSeriesError').textContent = 'Lütfen dizi/film adı girin.';
        document.getElementById('addSeriesError').style.display = 'block';
        return;
    }
    
    if (!url) {
        document.getElementById('addSeriesError').textContent = 'Lütfen video URL girin.';
        document.getElementById('addSeriesError').style.display = 'block';
        return;
    }
    
    // Check if user is logged in
    if (!currentUser || !currentUser.user_id) {
        document.getElementById('addSeriesError').textContent = 'Lütfen önce giriş yapın.';
        document.getElementById('addSeriesError').style.display = 'block';
        return;
    }
    
    // Show loading
    document.getElementById('addSeriesStatus').style.display = 'block';
    document.getElementById('addSeriesStatusText').textContent = 'Video indiriliyor ve işleniyor... Bu işlem birkaç dakika sürebilir.';
    document.getElementById('addSeriesError').style.display = 'none';
    document.getElementById('addSeriesSuccess').style.display = 'none';
    document.getElementById('addSeriesBtn').disabled = true;
    
    try {
        const response = await fetch('/api/custom-series/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                url: url,
                icon: icon,
                user_id: currentUser.user_id
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('addSeriesStatus').style.display = 'none';
            document.getElementById('addSeriesSuccess').innerHTML = `
                <strong>Başarılı!</strong><br>
                "${data.name}" eklendi.<br>
                <small>${data.unique_words} benzersiz kelime işlendi.</small>
            `;
            document.getElementById('addSeriesSuccess').style.display = 'block';
            
            // Reload custom series
            await loadCustomSeries();
            
            // Close modal after 2 seconds
            setTimeout(() => {
                closeAddSeriesModal();
            }, 2000);
        } else {
            document.getElementById('addSeriesStatus').style.display = 'none';
            document.getElementById('addSeriesError').textContent = data.error || 'Bir hata oluştu.';
            document.getElementById('addSeriesError').style.display = 'block';
            document.getElementById('addSeriesBtn').disabled = false;
        }
    } catch (error) {
        console.error('Error adding series:', error);
        document.getElementById('addSeriesStatus').style.display = 'none';
        document.getElementById('addSeriesError').textContent = 'Bağlantı hatası. Lütfen tekrar deneyin.';
        document.getElementById('addSeriesError').style.display = 'block';
        document.getElementById('addSeriesBtn').disabled = false;
    }
}

// Load Custom Series
async function loadCustomSeries() {
    try {
        const response = await fetch('/api/custom-series');
        const data = await response.json();
        
        if (data.success && data.series) {
            renderCustomSeries(data.series);
        }
    } catch (error) {
        console.error('Error loading custom series:', error);
    }
}

// Render Custom Series Cards
function renderCustomSeries(seriesList) {
    const container = document.getElementById('customSeriesContainer');
    const flashcardContainer = document.getElementById('customSeriesFlashcardContainer');
    
    if (container) {
        container.innerHTML = '';
    }
    if (flashcardContainer) {
        flashcardContainer.innerHTML = '';
    }
    
    seriesList.forEach(series => {
        // Card for main series selection area
        if (container) {
            const card = document.createElement('div');
            card.className = 'series-card custom-series-card';
            card.dataset.series = series.series_id;
            card.style.cssText = 'cursor: pointer; text-align: center; transition: transform 0.3s; position: relative; border: 2px solid transparent;';
            
            card.innerHTML = `
                <label style="position: absolute; top: 10px; right: 10px; cursor: pointer; z-index: 10;">
                    <input type="checkbox" class="series-checkbox" data-series="${series.series_id}" style="width: 20px; height: 20px; cursor: pointer;">
                </label>
                <button onclick="deleteCustomSeries('${series.series_id}', '${series.name}'); event.stopPropagation();" 
                        style="position: absolute; top: 10px; left: 10px; background: rgba(239, 68, 68, 0.9); color: white; border: none; border-radius: 50%; width: 24px; height: 24px; cursor: pointer; font-size: 0.8em; z-index: 10;" 
                        title="Sil">×</button>
                <div style="width: 150px; height: 225px; background: ${series.gradient}; border-radius: 12px; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px; box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);">
                    <span style="font-size: 3em;">${series.icon}</span>
                </div>
                <h3 style="margin: 0; font-size: 1.1em;">${series.name}</h3>
                <p style="color: #666; font-size: 0.8em; margin: 5px 0 0;">${series.total_episodes || 1} bölüm</p>
            `;
            
            // Add click handler for selection
            card.addEventListener('click', function(e) {
                if (e.target.type !== 'checkbox' && e.target.tagName !== 'BUTTON') {
                    const checkbox = this.querySelector('.series-checkbox');
                    if (checkbox) {
                        checkbox.checked = !checkbox.checked;
                        checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
            });
            
            container.appendChild(card);
        }
        
        // Card for flashcard study area (smaller version)
        if (flashcardContainer) {
            const flashcardCard = document.createElement('div');
            flashcardCard.className = 'series-card-flashcard custom-series-flashcard';
            flashcardCard.dataset.series = series.series_id;
            flashcardCard.dataset.customSeries = 'true';
            flashcardCard.style.cssText = 'cursor: pointer; text-align: center; transition: transform 0.3s; padding: 15px; border-radius: 12px; background: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.1);';
            
            flashcardCard.innerHTML = `
                <div style="width: 120px; height: 180px; background: ${series.gradient}; border-radius: 12px; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px; box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);">
                    <span style="font-size: 2.5em;">${series.icon}</span>
                </div>
                <h3 style="margin: 0; font-size: 1em;">${series.name}</h3>
                <p style="color: #666; font-size: 0.75em; margin: 5px 0 0;">${series.total_episodes || 1} bölüm</p>
            `;
            
            // Add click handler for flashcard selection
            flashcardCard.addEventListener('click', function() {
                selectCustomSeriesForFlashcard(series);
            });
            
            flashcardContainer.appendChild(flashcardCard);
        }
    });
    
    // Re-attach event listeners for new checkboxes
    attachSeriesCheckboxListeners();
}

// Attach event listeners to series checkboxes (including custom ones)
function attachSeriesCheckboxListeners() {
    document.querySelectorAll('.series-checkbox').forEach(checkbox => {
        checkbox.removeEventListener('change', handleSeriesCheckboxChange);
        checkbox.addEventListener('change', handleSeriesCheckboxChange);
    });
}

// Handle series checkbox change
function handleSeriesCheckboxChange() {
    const selectedCheckboxes = document.querySelectorAll('.series-checkbox:checked');
    const buildBtn = document.getElementById('buildWordMapBtn');
    const selectedText = document.getElementById('selectedSeriesText');
    
    if (selectedCheckboxes.length > 0) {
        buildBtn.disabled = false;
        const names = Array.from(selectedCheckboxes).map(cb => {
            const card = cb.closest('.series-card');
            const nameEl = card ? card.querySelector('h3') : null;
            return nameEl ? nameEl.textContent : cb.dataset.series;
        });
        selectedText.textContent = `Seçili: ${names.join(', ')}`;
    } else {
        buildBtn.disabled = true;
        selectedText.textContent = '';
    }
}

// Delete Custom Series
window.deleteCustomSeries = async function(seriesId, seriesName) {
    if (!confirm(`"${seriesName}" dizisini silmek istediğinizden emin misiniz?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/custom-series/${seriesId}/delete`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`"${seriesName}" silindi.`);
            await loadCustomSeries();
        } else {
            showNotification(data.error || 'Silme başarısız.', 'error');
        }
    } catch (error) {
        console.error('Error deleting series:', error);
        showNotification('Silme hatası.', 'error');
    }
}

// Load custom series on page load
document.addEventListener('DOMContentLoaded', function() {
    loadCustomSeries();
});

// ===== AI TRANSLATION FUNCTIONS =====

// Load translation statistics
async function loadTranslationStats() {
    try {
        const response = await fetch('/api/translate/stats');
        const data = await response.json();
        
        if (data.success) {
            const stats = data.stats;
            const container = document.getElementById('translationStatsContainer');
            
            if (container) {
                container.style.display = 'block';
                
                document.getElementById('translatedWordsCount').textContent = stats.words_with_definition;
                document.getElementById('untranslatedWordsCount').textContent = stats.words_without_definition;
                document.getElementById('translationProgressBar').style.width = stats.percentage + '%';
                document.getElementById('translationPercentage').textContent = stats.percentage + '%';
                document.getElementById('translationStatsText').textContent = 
                    `${stats.words_with_definition} / ${stats.total_words} kelime çevrilmiş`;
                
                // Update button text based on status
                const translateBtn = document.getElementById('translateAllWordsBtn');
                if (translateBtn) {
                    if (stats.words_without_definition === 0) {
                        translateBtn.innerHTML = '✅ Tüm Kelimeler Çevrildi';
                        translateBtn.disabled = true;
                    } else {
                        translateBtn.innerHTML = `🤖 ${stats.words_without_definition} Kelimeyi Çevir`;
                        translateBtn.disabled = false;
                    }
                }
            }
        }
    } catch (error) {
        console.error('Error loading translation stats:', error);
    }
}

// Translate all words without definitions
async function translateAllWords() {
    const translateBtn = document.getElementById('translateAllWordsBtn');
    const progressDiv = document.getElementById('translationProgress');
    const progressText = document.getElementById('translationProgressText');
    
    if (!translateBtn) return;
    
    // Disable button and show progress
    translateBtn.disabled = true;
    translateBtn.innerHTML = '⏳ Çevriliyor...';
    
    if (progressDiv) progressDiv.style.display = 'block';
    
    let totalTranslated = 0;
    let continueTranslation = true;
    
    try {
        // Translate in batches of 50
        while (continueTranslation) {
            if (progressText) {
                progressText.textContent = `${totalTranslated} kelime çevrildi, devam ediyor...`;
            }
            
            const response = await fetch('/api/translate/words', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ limit: 50, use_ai: true })
            });
            
            const data = await response.json();
            
            if (data.success) {
                totalTranslated += data.translated_count;
                
                if (data.translated_count === 0) {
                    // No more words to translate
                    continueTranslation = false;
                }
                
                // Update stats after each batch
                await loadTranslationStats();
            } else {
                console.error('Translation error:', data.error);
                continueTranslation = false;
            }
        }
        
        // Success message
        if (progressText) {
            progressText.textContent = `✅ Toplam ${totalTranslated} kelime başarıyla çevrildi!`;
        }
        
        setTimeout(() => {
            if (progressDiv) progressDiv.style.display = 'none';
        }, 3000);
        
        // Refresh the word map to show new definitions
        if (currentOpenPackageId) {
            const packages = await fetch(`/api/packages?user_id=${currentUser?.user_id}`).then(r => r.json());
            if (packages.success && packages.packages) {
                const pkg = packages.packages.find(p => p.id === currentOpenPackageId);
                if (pkg) {
                    loadLevelWords(currentOpenPackageId, pkg.package_name);
                }
            }
        }
        
    } catch (error) {
        console.error('Translation error:', error);
        if (progressText) {
            progressText.textContent = `❌ Hata: ${error.message}`;
        }
    } finally {
        // Re-enable button
        await loadTranslationStats();
    }
}

// Translate words in a specific package/level
async function translatePackageWords(packageId) {
    const btn = document.querySelector(`[data-translate-package="${packageId}"]`);
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ Çevriliyor...';
    }
    
    try {
        const response = await fetch(`/api/translate/package/${packageId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ limit: 500 })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`✅ ${data.translated_count} kelime çevrildi!`);
            
            // Reload the level words to show new definitions
            const packages = await fetch(`/api/packages?user_id=${currentUser?.user_id}`).then(r => r.json());
            if (packages.success && packages.packages) {
                const pkg = packages.packages.find(p => p.id === packageId);
                if (pkg) {
                    loadLevelWords(packageId, pkg.package_name);
                }
            }
            
            // Update translation stats
            await loadTranslationStats();
        } else {
            showNotification(`❌ Hata: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Package translation error:', error);
        showNotification(`❌ Çeviri hatası: ${error.message}`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '🤖 Bu Seviyeyi Çevir';
        }
    }
}

// Make functions globally available
window.translateAllWords = translateAllWords;
window.translatePackageWords = translatePackageWords;
window.loadTranslationStats = loadTranslationStats;

// Also load when switching to watch tab
const originalSwitchTab = window.switchTab;
if (typeof originalSwitchTab === 'function') {
    window.switchTab = function(tab) {
        originalSwitchTab(tab);
        if (tab === 'watch') {
            loadCustomSeries();
        }
    };
}

// Select custom series for flashcard study
window.selectCustomSeriesForFlashcard = async function(series) {
    // Highlight selected card
    document.querySelectorAll('.series-card-flashcard').forEach(card => {
        card.style.border = 'none';
        card.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
    });
    
    const selectedCard = document.querySelector(`.series-card-flashcard[data-series="${series.series_id}"]`);
    if (selectedCard) {
        selectedCard.style.border = '3px solid #667eea';
        selectedCard.style.boxShadow = '0 6px 20px rgba(102, 126, 234, 0.4)';
    }
    
    // Show episode selection area
    const selectionCard = document.getElementById('episodeSelectionCardFlashcard');
    if (selectionCard) {
        selectionCard.style.display = 'block';
        
        // Update title
        const titleEl = document.getElementById('selectedSeriesTitleFlashcard');
        if (titleEl) {
            titleEl.innerHTML = `${series.icon} ${series.name} - Bölüm Seçimi`;
        }
    }
    
    // Clear previous dataset values from load button
    const loadBtn = document.getElementById('loadEpisodeFlashcardsBtnFlashcard');
    if (loadBtn) {
        loadBtn.disabled = true;
        delete loadBtn.dataset.series;
        delete loadBtn.dataset.season;
        delete loadBtn.dataset.episode;
        delete loadBtn.dataset.customSeries;
        delete loadBtn.dataset.customEpisode;
    }
    
    // Hide episode info and flashcards from previous selection
    const episodeInfo = document.getElementById('episodeInfoFlashcard');
    if (episodeInfo) episodeInfo.style.display = 'none';
    const flashcardsSection = document.getElementById('flashcardsSectionFlashcard');
    if (flashcardsSection) flashcardsSection.style.display = 'none';
    const noFlashcardsMsg = document.getElementById('noFlashcardsMessageFlashcard');
    if (noFlashcardsMsg) noFlashcardsMsg.style.display = 'none';
    
    // Store selected custom series
    window.selectedCustomSeriesFlashcard = series;
    
    // Load episodes for this custom series
    try {
        const response = await fetch(`/api/custom-series/${series.series_id}/episodes`);
        const data = await response.json();
        
        if (data.success && data.episodes) {
            // Populate season select (for custom series, we use "episode" as season since it's simpler)
            const seasonSelect = document.getElementById('seriesSeasonSelectFlashcard');
            const episodeSelect = document.getElementById('seriesEpisodeSelectFlashcard');
            
            if (seasonSelect) {
                seasonSelect.innerHTML = '<option value="">Bölüm Seçin</option>';
                
                data.episodes.forEach((ep, index) => {
                    const option = document.createElement('option');
                    option.value = ep.episode_name || `episode_${index + 1}`;
                    option.textContent = `${ep.episode_name || 'Bölüm ' + (index + 1)} (${ep.word_count} kelime)`;
                    seasonSelect.appendChild(option);
                });
                
                // For custom series, directly enable flashcard loading on season select
                seasonSelect.onchange = function() {
                    const loadBtn = document.getElementById('loadEpisodeFlashcardsBtnFlashcard');
                    if (this.value) {
                        loadBtn.disabled = false;
                        // Set custom series data on the button
                        loadBtn.dataset.customSeries = series.series_id;
                        loadBtn.dataset.customEpisode = this.value;
                        // Clear normal series data
                        delete loadBtn.dataset.series;
                        delete loadBtn.dataset.season;
                        delete loadBtn.dataset.episode;
                        
                        // Hide episode select for custom series (not needed)
                        if (episodeSelect) {
                            episodeSelect.style.display = 'none';
                        }
                    } else {
                        loadBtn.disabled = true;
                        delete loadBtn.dataset.customSeries;
                        delete loadBtn.dataset.customEpisode;
                    }
                };
            }
            
            // Hide episode select for custom series
            if (episodeSelect) {
                episodeSelect.style.display = 'none';
            }
            
            // Setup load flashcards button
            const loadBtn = document.getElementById('loadEpisodeFlashcardsBtnFlashcard');
            if (loadBtn) {
                loadBtn.onclick = function() {
                    loadCustomSeriesFlashcards(series.series_id, seasonSelect.value);
                };
            }
        }
    } catch (error) {
        console.error('Error loading custom series episodes:', error);
    }
}

// Load flashcards for custom series
async function loadCustomSeriesFlashcards(seriesId, episodeName) {
    const userId = currentUser ? currentUser.user_id : localStorage.getItem('user_id');
    
    try {
        let url = `/api/custom-series/${seriesId}/flashcards?episode=${encodeURIComponent(episodeName)}`;
        if (userId) {
            url += `&user_id=${userId}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success) {
            // Show episode info
            const infoDiv = document.getElementById('episodeInfoFlashcard');
            if (infoDiv) {
                infoDiv.style.display = 'block';
                
                const titleEl = document.getElementById('episodeTitleFlashcard');
                if (titleEl) {
                    titleEl.textContent = `${data.series.name} - ${episodeName}`;
                }
                
                const wordCountEl = document.getElementById('episodeWordCountFlashcard');
                if (wordCountEl) {
                    wordCountEl.textContent = data.total_cards + data.known_count;
                }
                
                const flashcardCountEl = document.getElementById('episodeFlashcardCountFlashcard');
                if (flashcardCountEl) {
                    flashcardCountEl.textContent = data.total_cards;
                }
                
                const knownCountEl = document.getElementById('episodeKnownCountFlashcard');
                if (knownCountEl) {
                    knownCountEl.textContent = data.known_count;
                }
                
                const unknownCountEl = document.getElementById('episodeUnknownCountFlashcard');
                if (unknownCountEl) {
                    unknownCountEl.textContent = data.unknown_count;
                }
            }
            
            // Show flashcards section
            const flashcardsSection = document.getElementById('flashcardsSectionFlashcard');
            if (flashcardsSection && data.flashcards.length > 0) {
                flashcardsSection.style.display = 'block';
                
                // Store flashcards
                window.currentFlashcardsFlashcard = data.flashcards;
                window.currentFlashcardIndexFlashcard = 0;
                
                // Display first flashcard
                updateFlashcardDisplayFlashcard();
                updateFlashcardControlsFlashcard();
            } else if (flashcardsSection) {
                flashcardsSection.style.display = 'none';
                const noFlashcardsMsg = document.getElementById('noFlashcardsMessageFlashcard');
                if (noFlashcardsMsg) {
                    noFlashcardsMsg.style.display = 'block';
                }
            }
        } else {
            console.error('Error loading flashcards:', data.error);
            showNotification(data.error || 'Flashcard yüklenemedi', 'error');
        }
    } catch (error) {
        console.error('Error loading custom series flashcards:', error);
        showNotification('Bağlantı hatası', 'error');
    }
}

// Update flashcard display for custom series flashcard area
function updateFlashcardDisplayFlashcard() {
    if (!window.currentFlashcardsFlashcard || window.currentFlashcardsFlashcard.length === 0) return;
    
    const card = window.currentFlashcardsFlashcard[window.currentFlashcardIndexFlashcard];
    
    const wordEl = document.getElementById('flashcardWordFlashcard');
    const defEl = document.getElementById('flashcardDefinitionFlashcard');
    const pronEl = document.getElementById('flashcardPronunciationFlashcard');
    const freqEl = document.getElementById('flashcardFrequencyFlashcard');
    
    if (wordEl) wordEl.textContent = card.word;
    if (defEl) defEl.textContent = card.definition || '(Çeviri henüz eklenmemiş)';
    if (pronEl) pronEl.textContent = card.pronunciation || '';
    if (freqEl) freqEl.textContent = card.frequency ? `Frekans: ${card.frequency}` : '';
}

// Update flashcard controls for custom series flashcard area
function updateFlashcardControlsFlashcard() {
    if (!window.currentFlashcardsFlashcard) return;
    
    const total = window.currentFlashcardsFlashcard.length;
    const current = window.currentFlashcardIndexFlashcard + 1;
    
    const counterEl = document.getElementById('flashcardCounterFlashcard');
    if (counterEl) {
        counterEl.textContent = `${current} / ${total}`;
    }
    
    const prevBtn = document.getElementById('prevFlashcardBtnFlashcard');
    const nextBtn = document.getElementById('nextFlashcardBtnFlashcard');
    const markKnownBtn = document.getElementById('markKnownBtnFlashcard');
    const markUnknownBtn = document.getElementById('markUnknownBtnFlashcard');
    
    if (prevBtn) prevBtn.disabled = window.currentFlashcardIndexFlashcard === 0;
    if (nextBtn) nextBtn.disabled = window.currentFlashcardIndexFlashcard >= total - 1;
    if (markKnownBtn) markKnownBtn.disabled = false;
    if (markUnknownBtn) markUnknownBtn.disabled = false;
}
