import sys
import os

# Ensure parent directory is in Python path for Vercel Serverless
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app import app

# Vercel Serverless WSGI Path Middleware
# Vercel rewrites incoming requests to /api/index, causing Flask to receive /api/index instead of /
class VercelPathFixMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        # Strip /api/index prefix if injected by Vercel rewrite
        if path.startswith('/api/index'):
            path = path[len('/api/index'):]
            environ['PATH_INFO'] = path if path else '/'
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
