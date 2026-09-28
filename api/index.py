import sys
import os
import traceback

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from app import app as real_app
    app = real_app
except Exception as e:
    from flask import Flask
    app = Flask(__name__)
    err_tb = traceback.format_exc()
    
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        return f"<html><body><h2>Import Error:</h2><pre>{err_tb}</pre></body></html>", 500
