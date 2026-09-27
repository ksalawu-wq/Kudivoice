"""
app.py — Top-level FastAPI application entrypoint for Vercel & local server.
Integrates teammates' backend (api.py) and mounts the frontend UI.
"""

from __future__ import annotations

import os
from pathlib import Path
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Import teammates' pre-configured FastAPI app
from api import app

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Mount static CSS & JS directories
css_dir = FRONTEND_DIR / "css"
if css_dir.exists():
    app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")

js_dir = FRONTEND_DIR / "js"
if js_dir.exists():
    app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")

# Serve the Impeccable Frontend UI at root "/"
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return "<h1>KudiVoice AI</h1>"

# Local server launcher
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 KudiVoice AI running at: http://localhost:{port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
