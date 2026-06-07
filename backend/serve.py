import argparse

import uvicorn

from app.main import app


# The PyInstaller-packaged backend entry point also uses this set of arguments; the Electron main process passes in host/port.
def parse_args() -> argparse.Namespace:
    """Parse the backend startup arguments.

    Returns:
        A command-line arguments object containing only host and port.
    """
    parser = argparse.ArgumentParser(description="Run the OC Creative Assistant backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    return parser.parse_args()


def main() -> None:
    """Start the uvicorn service according to the command-line arguments."""
    args = parse_args()
    # The desktop app's process lifecycle is managed by Electron; reload is disabled in packaged mode.
    uvicorn.run(app, host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
