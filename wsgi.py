"""
WSGI wrapper for Render deployment
Imports the FastAPI app from backend/main.py so Gunicorn can find it
"""
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# Import the FastAPI app
from main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
