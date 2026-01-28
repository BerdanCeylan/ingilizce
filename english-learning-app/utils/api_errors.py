"""
API error response helpers.
Log full errors server-side; return safe, generic messages to clients in production.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

from flask import jsonify

LOG = logging.getLogger(__name__)


def _is_debug() -> bool:
    v = os.getenv('FLASK_DEBUG', os.getenv('DEBUG', '0'))
    return str(v).lower() in ('1', 'true', 'yes')


def api_error_500(e: Exception, extra: Optional[Dict[str, Any]] = None) -> Tuple[Any, int]:
    """
    Log exception (with traceback) and return 500 JSON response.
    In production, avoids exposing str(e) to clients; use FLASK_DEBUG=1 for details.
    """
    LOG.exception("API error: %s", e)
    payload: Dict[str, Any] = {'success': False}
    if _is_debug():
        payload['error'] = str(e)
        if extra:
            payload.update(extra)
    else:
        payload['error'] = 'Internal server error'
    return jsonify(payload), 500
