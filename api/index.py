import sys
import os

# Add parent directory to python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import app

# Export app & handler for Vercel WSGI / Serverless runtime
app = app
handler = app
