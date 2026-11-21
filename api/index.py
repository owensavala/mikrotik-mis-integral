import sys
import os
import urllib.parse

# Ensure parent directory is in Python path for Vercel Serverless
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app import app

# Vercel Serverless WSGI Path Middleware
# Vercel rewrites incoming requests to /api/index?__vercel_path=/$1
class VercelPathFixMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # 1. Check explicit rewrite query parameter
        query_string = environ.get('QUERY_STRING', '')
        if '__vercel_path=' in query_string:
            qs = urllib.parse.parse_qs(query_string)
            if '__vercel_path' in qs:
                real_path = qs['__vercel_path'][0]
                if not real_path.startswith('/'):
                    real_path = '/' + real_path
                # Normalize double slashes
                while '//' in real_path:
                    real_path = real_path.replace('//', '/')
                environ['PATH_INFO'] = real_path
                
                # Clean up query string
                cleaned = {k: v for k, v in qs.items() if k != '__vercel_path'}
                environ['QUERY_STRING'] = urllib.parse.urlencode(cleaned, doseq=True)
                return self.wsgi_app(environ, start_response)

        # 2. Check forwarded headers if query param not present
        forwarded = (
            environ.get('HTTP_X_FORWARDED_PATH') or
            environ.get('HTTP_X_MATCHED_PATH') or
            environ.get('HTTP_X_ORIGINAL_URL') or
            environ.get('RAW_URI') or
            environ.get('REQUEST_URI')
        )
        if forwarded:
            path = forwarded.split('?')[0]
            if path == '/api/index':
                path = '/'
            environ['PATH_INFO'] = path
        else:
            path = environ.get('PATH_INFO', '')
            if path.startswith('/api/index'):
                path = path[len('/api/index'):]
                environ['PATH_INFO'] = path if path else '/'
                
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
