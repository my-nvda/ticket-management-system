import sys
import os
import traceback

# Add root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    from app import app
    handler = app
except Exception as e:
    from flask import Flask
    app = Flask(__name__)
    err_tb = traceback.format_exc()
    
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        return f"<pre style='color:red; font-size:14px; padding:20px; background:#111;'>Vercel App Initialization Error:\n{err_tb}</pre>", 500
    
    handler = app
