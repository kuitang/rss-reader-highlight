"""Entry point for python -m app"""
import os
import sys
import uvicorn
from .main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    production = os.getenv("PRODUCTION", "false").lower() == "true"

    if production:
        print(f"Starting production server on 0.0.0.0:{port}")
        uvicorn.run(app, host="0.0.0.0", port=port,
                   log_level="info", access_log=False,
                   server_header=False, date_header=False)
    else:
        print(f"Starting development server on 0.0.0.0:{port}")
        uvicorn.run("app.main:app", host="0.0.0.0", port=port,
                   reload=True, reload_dirs=["app"],
                   reload_excludes=["data/*", "*.db", "__pycache__/*"])