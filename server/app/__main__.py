"""Run the server: python -m app  (from the server/ folder). Binds to 127.0.0.1 only."""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), log_level="info")
