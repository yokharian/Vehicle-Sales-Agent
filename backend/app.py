"""Vercel entrypoint for the WhatsApp assistant.

Vercel loads a top-level ``app`` from ``app.py``. Application modules import
as flat siblings, so ``src`` is placed on ``sys.path`` before that import.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from whatsapp_server import create_fastapi_app

app = create_fastapi_app()
