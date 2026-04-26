"""Frozen executable entry point for AI Image 2."""

import os

import uvicorn

import app as app_module


def main() -> None:
    host = os.environ.get("AI_IMAGE_HOST", "127.0.0.1")
    port = int(os.environ.get("AI_IMAGE_PORT", "8012"))
    uvicorn.run(
        app_module.app,
        host=host,
        port=port,
        reload=False,
        loop="asyncio",
        http="h11",
        lifespan="on",
    )


if __name__ == "__main__":
    main()
