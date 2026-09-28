import sys
import os

# Add parent directory to python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import app

# Export for Vercel Serverless Function
app = app
