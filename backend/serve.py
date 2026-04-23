import argparse

import uvicorn

from main import app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the OC Creative Assistant backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    uvicorn.run(app, host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
