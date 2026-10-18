"""Portable host/port handling for local and hosted startup."""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "weave_brain.api.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
