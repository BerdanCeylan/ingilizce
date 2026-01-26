# 🎬 English Learning - Video Analyzer

A web application that extracts vocabulary from English videos using speech-to-text technology. Learn new words from your favorite videos with an interactive interface!

## Features

- 🎥 **Video Processing**: Extract words from video files using speech-to-text
- 📚 **Vocabulary Management**: Track known and unknown words
- 📊 **Learning Progress**: Monitor your learning progress with detailed statistics
- 👤 **User Profiles**: Multiple user support with personalized word databases
- 🔍 **Smart Filtering**: Filter words by frequency and learning status
- 🎯 **Interactive Learning**: Mark words as known/unknown to track progress

## System Architecture

### Backend
- **Framework**: Flask (Python)
- **Database**: SQLite3
- **Speech-to-Text**: OpenAI Whisper API or Local Whisper
- **Audio Processing**: FFmpeg, LibROSA, SoundFile

### Frontend
- **HTML5/CSS3**: Modern, responsive UI
- **JavaScript**: Interactive features without external frameworks
- **Features**: Real-time updates, progress tracking, word filtering

## Prerequisites

- Python 3.8+
- FFmpeg (for audio extraction from videos)
- pip (Python package manager)

### Install FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt-get install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html or use:
```bash
choco install ffmpeg
```

## Installation

1. **Clone/Download the project:**
```bash
cd english-learning-app
```

2. **Create a virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Download Whisper model (optional, for local transcription):**
```bash
pip install openai-whisper
```

## Configuration

### Option 1: Using OpenAI Whisper API (Recommended)

Get better transcription accuracy with the cloud API:

1. Get an API key from https://platform.openai.com/api-keys
2. Create `.env` file in project root:
```
OPENAI_API_KEY=your_api_key_here
```

3. In `app.py`, change:
```python
speech_processor = SpeechProcessor(use_openai=True)
```

### Option 2: Using Local Whisper (Free but slower)

Uses the local model - no API key needed, but slower processing.

```python
speech_processor = SpeechProcessor(use_openai=False)
```

## Video Directory Setup

1. Create video files in: `/home/duffyduck/Downloads/ingilizce`

Supported formats: `.mp4`, `.avi`, `.mkv`, `.mov`, `.webm`, `.flv`, `.wmv`

2. The app will automatically process all videos in this directory.

## Running the Application

1. **Start the Flask server:**
```bash
python app.py
```

2. **Open in browser:**
```
http://localhost:5000
```

3. **Enter your username** and click "Start Learning"

4. **Process videos:**
   - Click "🎬 Process Videos"
   - Wait for transcription to complete
   - View extracted words

5. **Mark words:**
   - Click ✅ for words you know
   - Click ❌ for words you want to learn

6. **Track progress:**
   - View statistics in "📊 Statistics" tab
   - See processed videos in "🎥 Videos" tab

## Database Structure

### `users` table
- Stores user information and creation timestamps

### `words` table
- Maintains the master vocabulary database
- Tracks word frequency across all videos

### `user_words` table
- Links users to words with learning status
- Stores "known" flag and last update timestamp

### `videos` table
- Records processed video files and word counts

## API Endpoints

```
POST   /api/users                 - Create/get user
POST   /api/process-videos        - Process all videos in directory
GET    /api/words                 - Get user's words (with filters)
POST   /api/words/<id>/mark       - Mark word as known/unknown
GET    /api/stats                 - Get learning statistics
GET    /api/videos                - Get processed videos
```

## Troubleshooting

### "Module not found" errors
```bash
pip install -r requirements.txt
```

### FFmpeg not found
Make sure FFmpeg is installed and in your system PATH:
```bash
ffmpeg -version
```

### Slow transcription
- Switch to OpenAI API for faster processing (requires API key)
- Or use smaller Whisper model (base vs large)

### Database issues
Delete `learning.db` to reset database:
```bash
rm learning.db
python app.py
```

## Workflow

1. **User Setup**: Enter your name to create user profile
2. **Video Processing**: 
   - System reads all videos from `/home/duffyduck/Downloads/ingilizce`
   - Extracts audio from each video
   - Converts speech to text
   - Extracts unique words (filters common words)
3. **Database Storage**:
   - New words added to main vocabulary
   - User gets assigned all extracted words
4. **Learning Interface**:
   - Browse all words extracted from videos
   - Mark words as "Know" or "Don't Know"
   - Track learning progress with statistics

## Performance Tips

1. **Batch Processing**: Process videos during off-peak hours
2. **API Limits**: OpenAI has rate limits - check your plan
3. **Large Videos**: Longer videos take more time to transcribe
4. **Database Optimization**: SQLite works well for this use case

## Future Enhancements

- 🎤 Real-time recording support
- 📱 Mobile app version
- 🌐 Multiple language support
- 🎓 Spaced repetition algorithm
- 📈 Advanced analytics
- 💾 Export/import word lists
- 🔊 Word pronunciation audio

## License

This project is open source and available for educational use.

## Support

For issues or questions, check the troubleshooting section or review the code comments.

---

**Happy Learning! 🚀**
