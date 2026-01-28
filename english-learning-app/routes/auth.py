"""
Authentication Routes Blueprint
Handles user registration, login, and Google OAuth
"""
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Tuple, Optional
import requests
import os

from utils.api_errors import api_error_500

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Database instance will be injected via init function
_db = None

def init_auth_routes(db):
    """Initialize auth routes with database instance"""
    global _db
    _db = db
    
    @auth_bp.route('/register', methods=['POST'])
    def register() -> Tuple:
        """Register new user"""
        data = request.get_json()
        if data is None:
            return jsonify({'success': False, 'error': 'Invalid request'}), 400
        
        username: Optional[str] = data.get('username')
        password: Optional[str] = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Kullanıcı adı ve şifre gerekli'}), 400
        
        password_hash = generate_password_hash(password)
        success, user_id, message = _db.register_user(username, password_hash)
        
        if success:
            return jsonify({'success': True, 'user_id': user_id, 'username': username, 'message': message}), 200
        else:
            return jsonify({'success': False, 'error': message}), 400

    @auth_bp.route('/login', methods=['POST'])
    def login() -> Tuple:
        """Login user"""
        data = request.get_json()
        if data is None:
            return jsonify({'success': False, 'error': 'Invalid request'}), 400
        
        password: Optional[str] = data.get('password')
        username: Optional[str] = data.get('username')
        if not username or not password:
            return jsonify({'success': False, 'error': 'Kullanıcı adı ve şifre gerekli'}), 400
        
        user = _db.get_user_by_username(username)
        
        if user and user['password_hash'] and check_password_hash(user['password_hash'], password):
            return jsonify({'success': True, 'user_id': user['id'], 'username': user['username']}), 200
        else:
            return jsonify({'success': False, 'error': 'Geçersiz kullanıcı adı veya şifre'}), 401

    @auth_bp.route('/google', methods=['POST'])
    def google_auth() -> Tuple:
        """Handle Google Sign-In"""
        data = request.get_json()
        if data is None:
            return jsonify({'success': False, 'error': 'Invalid request'}), 400
        
        token: Optional[str] = data.get('token')
        
        if not token:
            return jsonify({'success': False, 'error': 'Token gerekli'}), 400
        
        try:
            # Verify token with Google
            response = requests.get(f'https://oauth2.googleapis.com/tokeninfo?id_token={token}')
            if response.status_code != 200:
                return jsonify({'success': False, 'error': 'Geçersiz Google token'}), 401
                
            google_data = response.json()
            email: Optional[str] = google_data.get('email')
            google_id: Optional[str] = google_data.get('sub')
            name: str = google_data.get('name', email.split('@')[0]) if email else 'user'
            picture: str = google_data.get('picture', '')
            
            user_id, username = _db.login_with_google(email or '', google_id or '', name, picture)
            
            return jsonify({'success': True, 'user_id': user_id, 'username': username}), 200
        except Exception as e:
            return api_error_500(e)
