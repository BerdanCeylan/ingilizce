/**
 * Room Management Module
 * Handles watch room operations
 */
import { state } from './state.js';
import { switchTab } from './ui.js';
import { apiGet, apiPost } from './api.js';

/**
 * Load all active rooms
 */
export async function loadRooms() {
    try {
        const data = await apiGet('/api/rooms');
        if (data.success) {
            displayRooms(data.rooms);
        } else {
            console.error('Load rooms error:', data.error);
        }
    } catch (err) {
        console.error('❌ Error loading rooms:', err);
    }
}

/**
 * Display rooms in the UI
 */
function displayRooms(rooms) {
    const roomsList = document.getElementById('roomsList');
    
    if (!roomsList) return;
    
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

/**
 * Create a new room
 */
export async function createNewRoom() {
    const roomName = document.getElementById('roomName')?.value.trim();
    const videoUrl = document.getElementById('videoUrl')?.value.trim();
    const videoTitle = document.getElementById('videoTitle')?.value.trim();

    if (!roomName) {
        alert('Lütfen oda adı girin');
        return;
    }

    if (!state.currentUser || !state.currentUser.user_id) {
        alert('Lütfen önce giriş yapın');
        return;
    }

    try {
        const data = await apiPost('/api/rooms', {
            room_name: roomName,
            user_id: state.currentUser.user_id,
            video_url: videoUrl,
            video_title: videoTitle
        });

        if (data.success) {
            alert('✅ Oda oluşturuldu!');
            await joinRoom(data.room_id);
            loadRooms();
            
            // Clear form
            const roomNameInput = document.getElementById('roomName');
            const videoUrlInput = document.getElementById('videoUrl');
            const videoTitleInput = document.getElementById('videoTitle');
            if (roomNameInput) roomNameInput.value = 'Benim Odası';
            if (videoUrlInput) videoUrlInput.value = '';
            if (videoTitleInput) videoTitleInput.value = '';
        } else {
            alert('❌ Hata: ' + (data.error || 'Oda oluşturulamadı'));
        }
    } catch (err) {
        console.error('❌ Create room error:', err);
        alert('Oda oluşturulurken hata oluştu: ' + err.message);
    }
}

/**
 * Join a room
 */
export async function joinRoom(roomId) {
    if (!state.currentUser || !state.currentUser.user_id) {
        alert('Odaya katılmak için giriş yapmanız gerekiyor.');
        return;
    }

    // If already in a different room, leave it first
    if (state.currentRoom && state.currentRoom !== roomId) {
        await leaveRoom();
    }

    try {
        const data = await apiPost(`/api/rooms/${roomId}/join`, {
            user_id: state.currentUser.user_id
        });

        if (data.success) {
            state.currentRoom = roomId;
            
            // Socket emit (if socket exists)
            if (state.socket) {
                state.socket.emit('join_room', {
                    room_id: roomId,
                    user_id: state.currentUser.user_id,
                    username: state.currentUser.username
                });
            }

            if (window.loadRoomDetails) window.loadRoomDetails(roomId);
            if (window.loadRoomVideoStats) window.loadRoomVideoStats(roomId);
            switchTab('watch');
        } else {
            alert('❌ Hata: ' + (data.error || data.message || 'Bilinmeyen hata'));
        }
    } catch (err) {
        console.error('❌ Join room error:', err);
        alert('❌ Odaya katılırken hata oluştu: ' + err.message);
    }
}

/**
 * Leave current room
 */
export async function leaveRoom() {
    if (!state.currentRoom || !state.currentUser) {
        return;
    }

    try {
        await apiPost(`/api/rooms/${state.currentRoom}/leave`, {
            user_id: state.currentUser.user_id
        });

        if (state.socket) {
            state.socket.emit('leave_room', {
                room_id: state.currentRoom,
                user_id: state.currentUser.user_id
            });
        }

        state.currentRoom = null;
        
        // Hide watch section
        const watchTab = document.getElementById('watchTab');
        if (watchTab) watchTab.style.display = 'none';
        
        // Switch to rooms tab
        switchTab('rooms');
    } catch (err) {
        console.error('Leave room error:', err);
    }
}

// Export for global access
window.loadRooms = loadRooms;
window.createNewRoom = createNewRoom;
window.joinRoom = joinRoom;
window.leaveRoom = leaveRoom;
