"""
Routes package - Contains all Flask Blueprints
"""
from flask import Blueprint

# Import available blueprints (only those that exist)
from .auth import auth_bp
from .rooms import rooms_bp
from .chatbot import chatbot_bp

# TODO: Create these blueprints when needed
# from .series import series_bp
# from .videos import videos_bp
# from .words import words_bp
# from .packages import packages_bp
# from .subtitles import subtitles_bp
# from .flashcards import flashcards_bp
# from .custom_series import custom_series_bp
# from .profile import profile_bp

__all__ = [
    'auth_bp',
    'rooms_bp',
    'chatbot_bp',
    # 'series_bp',
    # 'videos_bp',
    # 'words_bp',
    # 'packages_bp',
    # 'subtitles_bp',
    # 'flashcards_bp',
    # 'custom_series_bp',
    # 'profile_bp',
]
