"""
Watch Room Routes Blueprint
Handles room creation, joining, leaving, and room-related operations
"""
from flask import Blueprint, request, jsonify
from typing import Tuple, Optional

rooms_bp = Blueprint('rooms', __name__, url_prefix='/api/rooms')

# Database instance will be injected via init function
_db = None

def init_rooms_routes(db):
    """Initialize rooms routes with database instance"""
    global _db
    _db = db
    
    @rooms_bp.route('', methods=['GET'])
    def get_rooms():
        """Get all active rooms"""
        rooms_list = _db.get_active_rooms()
        return jsonify({
            'success': True,
            'rooms': rooms_list
        })

    @rooms_bp.route('', methods=['POST'])
    def create_room() -> Tuple:
        """Create a new watch room"""
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request'}), 400
        
        room_name: str = data.get('room_name', 'Untitled Room')
        creator_id: Optional[int] = data.get('user_id')
        video_url: str = data.get('video_url', '')
        video_title: str = data.get('video_title', 'Video')
        
        if not creator_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
        
        room_id = _db.create_room(room_name, creator_id, video_url, video_title)
        
        return jsonify({
            'success': True,
            'room_id': room_id,
            'room_name': room_name
        }), 200

    @rooms_bp.route('/<int:room_id>', methods=['GET'])
    def get_room_details(room_id: int) -> Tuple:
        """Get room details including members and messages"""
        room = _db.get_room(room_id)
        if not room:
            return jsonify({'success': False, 'error': 'Room not found'}), 404

        members = _db.get_room_members(room_id)
        messages = _db.get_room_messages(room_id)
        
        return jsonify({
            'success': True,
            'room': room,
            'members': members,
            'messages': messages
        }), 200

    @rooms_bp.route('/<int:room_id>/join', methods=['POST'])
    def join_watch_room(room_id: int) -> Tuple:
        """Add user to room"""
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request'}), 400
        
        user_id: Optional[int] = data.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
        
        # Try to add member
        if _db.add_member_to_room(room_id, user_id):
            return jsonify({'success': True, 'message': 'Joined room'}), 200
        
        # If failed, check if already a member (treat as success for re-join)
        members = _db.get_room_members(room_id)
        is_member = any(m['id'] == user_id for m in members)
        
        if is_member:
            return jsonify({'success': True, 'message': 'Rejoined room'}), 200
        
        return jsonify({'success': False, 'error': 'Could not join room'}), 400

    @rooms_bp.route('/<int:room_id>/leave', methods=['POST'])
    def leave_watch_room(room_id: int) -> Tuple:
        """Remove user from room"""
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request'}), 400
        
        user_id: Optional[int] = data.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
        
        success = _db.remove_member_from_room(room_id, user_id)
        
        # Check if room is empty and close it
        members = _db.get_room_members(room_id)
        if not members:
            _db.close_room(room_id)
        
        return jsonify({
            'success': success
        }), 200

    @rooms_bp.route('/<int:room_id>/stats', methods=['GET'])
    def get_room_video_stats(room_id: int) -> Tuple:
        """Get vocabulary stats for the video in the room"""
        user_id_str = request.args.get('user_id')
        if not user_id_str:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
            
        user_id = int(user_id_str)
        stats = _db.get_video_stats_for_room(room_id, user_id)
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200

    @rooms_bp.route('/<int:room_id>/words', methods=['GET'])
    def get_room_video_words(room_id: int) -> Tuple:
        """Get words for the video in the room"""
        user_id_str = request.args.get('user_id')
        status: str = request.args.get('status', 'all')
        
        if not user_id_str:
            return jsonify({'success': False, 'error': 'User ID required'}), 400
            
        user_id = int(user_id_str)
        words = _db.get_room_video_words(room_id, user_id, status)
        return jsonify({'success': True, 'words': words}), 200
