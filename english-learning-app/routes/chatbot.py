"""
Chatbot Routes Blueprint
Handles AI chatbot interactions for English learning
"""
from flask import Blueprint, request, jsonify
from typing import Tuple
import sys
import os

from utils.api_errors import api_error_500

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from utils.chatbot import get_chatbot
except ImportError as e:
    import traceback
    print(f"Warning: Could not import chatbot module: {e}")
    print(traceback.format_exc())
    # Create a dummy function to prevent import errors
    def get_chatbot():
        raise Exception(f"Chatbot module not available: {e}")

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/api/chatbot')

@chatbot_bp.route('/chat', methods=['POST'])
def chat() -> Tuple:
    """Handle chatbot chat request"""
    try:
        data = request.get_json()
        if data is None:
            return jsonify({'success': False, 'error': 'Invalid request'}), 400
        
        user_message = data.get('message', '').strip()
        user_id = data.get('user_id')  # Optional user ID
        
        if not user_message:
            return jsonify({
                'success': False,
                'error': 'Message is required'
            }), 400
        
        # Get chatbot instance and generate response
        chatbot = get_chatbot()
        result = chatbot.chat(user_message, user_id)
        
        return jsonify({
            'success': True,
            'response': result['response'],
            'model_used': result.get('model_used', 'unknown'),
            'timestamp': result.get('timestamp')
        }), 200
        
    except Exception as e:
        return api_error_500(e)

@chatbot_bp.route('/clear', methods=['POST'])
def clear_history() -> Tuple:
    """Clear conversation history"""
    try:
        chatbot = get_chatbot()
        result = chatbot.clear_history()
        return jsonify({
            'success': True,
            'message': result['message']
        }), 200
    except Exception as e:
        return api_error_500(e)

@chatbot_bp.route('/history', methods=['GET'])
def get_history() -> Tuple:
    """Get conversation history"""
    try:
        chatbot = get_chatbot()
        history = chatbot.get_history()
        return jsonify({
            'success': True,
            'history': history
        }), 200
    except Exception as e:
        return api_error_500(e)

@chatbot_bp.route('/status', methods=['GET'])
def get_status() -> Tuple:
    """Get chatbot status"""
    try:
        chatbot = get_chatbot()
        return jsonify({
            'success': True,
            'model_loaded': chatbot.model_loaded,
            'model_available': chatbot.model_loaded,
            'history_length': len(chatbot.conversation_history)
        }), 200
    except Exception as e:
        return api_error_500(e)
