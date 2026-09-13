import sys
import urllib.parse
from pathlib import Path

# Ensure root directory is on Python module search path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from webapp_server import app as fastapi_app


class VercelPathMiddleware:
    """
    Restores the original request URL from the `_path` query parameter populated by Vercel rewrites.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            query_string = scope.get("query_string", b"").decode("utf-8")
            if query_string:
                query_params = urllib.parse.parse_qs(query_string, keep_blank_values=True)
                if "_path" in query_params:
                    rel_path = query_params.pop("_path")[0]
                    scope["path"] = f"/api/{rel_path}".rstrip("/") if rel_path else "/api"
                    scope["query_string"] = urllib.parse.urlencode(query_params, doseq=True).encode("utf-8")
        await self.app(scope, receive, send)


app = VercelPathMiddleware(fastapi_app)
