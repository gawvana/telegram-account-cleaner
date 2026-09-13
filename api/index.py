import os
import sys
from pathlib import Path

# Ensure root directory is on Python module search path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from webapp_server import app as fastapi_app


class VercelPathMiddleware:
    """
    Middleware for Vercel Serverless Functions.
    Restores the original request URL from `x-matched-path` header when internal rewrites occur.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            # Vercel sends the client-facing requested URL path in x-matched-path
            matched_path = headers.get(b"x-matched-path")
            if matched_path:
                decoded_path = matched_path.decode("utf-8")
                scope["path"] = decoded_path
            else:
                path = scope.get("path", "")
                if path.startswith("/api/index.py"):
                    scope["path"] = path.replace("/api/index.py", "/api", 1)
        await self.app(scope, receive, send)


app = VercelPathMiddleware(fastapi_app)
