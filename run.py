"""
Local runner for the Google Maps Lead Intelligence prototype.

Use this file on Windows instead of calling uvicorn directly.
It configures the Windows Proactor event loop required by
Playwright's async subprocess handling.
"""

import asyncio
import platform

import uvicorn


def main() -> None:
    # Playwright's async browser launcher relies on subprocesses.
    # On Windows, use the Proactor event loop for subprocess support.
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(
            asyncio.WindowsProactorEventLoopPolicy()
        )

    uvicorn.run(
        "backend.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()