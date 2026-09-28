import sys
import os

# Explicitly add repository root directory to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

# Export for Vercel serverless WSGI runtime
app = app
