/**
 * Video Processing Module
 * Handles video processing and management
 */
import { state } from './state.js';
import { apiGet, apiPost } from './api.js';

/**
 * Process all videos in directory
 */
export async function processVideos() {
    const btn = document.getElementById('processBtn');
    const status = document.getElementById('processingStatus');
    const result = document.getElementById('processResult');

    if (!btn || !status || !result) return;

    if (!state.currentUser || !state.currentUser.user_id) {
        alert('Video işlemek için giriş yapmanız gerekiyor.');
        return;
    }

    btn.disabled = true;
    status.style.display = 'block';
    result.style.display = 'none';

    try {
        const data = await apiPost('/api/process-videos', {
            user_id: state.currentUser.user_id
        });

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
            
            // Reload data
            setTimeout(() => {
                if (window.loadWords) window.loadWords();
                if (window.loadVideos) window.loadVideos();
            }, 500);
        } else {
            result.innerHTML = `<div style="background: #fee2e2; border: 1px solid #fca5a5; padding: 15px; border-radius: 8px; color: #dc2626;">❌ Hata: ${data.error}</div>`;
            result.style.display = 'block';
        }
    } catch (err) {
        status.style.display = 'none';
        result.innerHTML = '<div style="background: #fee2e2; padding: 15px; border-radius: 8px; color: #dc2626;">❌ İstek hatası</div>';
        result.style.display = 'block';
        console.error('Error:', err);
    } finally {
        btn.disabled = false;
    }
}

/**
 * Process video from URL
 */
export async function processVideoUrl() {
    const urlInput = document.getElementById('learnVideoUrl');
    const url = urlInput?.value.trim();
    const btn = document.getElementById('processUrlBtn');
    const status = document.getElementById('urlProcessingStatus');
    const result = document.getElementById('urlProcessResult');

    if (!url) {
        alert('Lütfen bir URL girin');
        return;
    }

    if (!state.currentUser || !state.currentUser.user_id) {
        alert('Video işlemek için giriş yapmanız gerekiyor.');
        return;
    }

    if (!btn || !status || !result) return;

    btn.disabled = true;
    status.style.display = 'block';
    result.style.display = 'none';

    try {
        const data = await apiPost('/api/process-video-url', {
            user_id: state.currentUser.user_id,
            video_url: url
        });

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
            if (urlInput) urlInput.value = '';
            
            // Reload data
            setTimeout(() => {
                if (window.loadWords) window.loadWords();
                if (window.loadVideos) window.loadVideos();
            }, 500);
        } else {
            result.innerHTML = `<div style="background: #fee2e2; border: 1px solid #fca5a5; padding: 15px; border-radius: 8px; color: #dc2626;">❌ Hata: ${data.error}</div>`;
            result.style.display = 'block';
        }
    } catch (err) {
        status.style.display = 'none';
        result.innerHTML = '<div style="background: #fee2e2; padding: 15px; border-radius: 8px; color: #dc2626;">❌ İstek hatası</div>';
        result.style.display = 'block';
        console.error('Error:', err);
    } finally {
        btn.disabled = false;
    }
}

/**
 * Load videos list
 */
export async function loadVideos() {
    if (!state.currentUser) return;

    try {
        const data = await apiGet(`/api/videos?user_id=${state.currentUser.user_id}`);
        if (data.success) {
            if (window.displayVideos) {
                window.displayVideos(data.videos);
            }
        }
    } catch (err) {
        console.error('Error loading videos:', err);
    }
}

// Export for global access
window.processVideos = processVideos;
window.processVideoUrl = processVideoUrl;
window.loadVideos = loadVideos;
