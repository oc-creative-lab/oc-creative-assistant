import argparse

import uvicorn

from main import app


# PyInstaller 打包后的后端入口也走这套参数，Electron 主进程会传入 host/port。
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the OC Creative Assistant backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    # 桌面应用由 Electron 管理进程生命周期，打包态不启用 reload。
    uvicorn.run(app, host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
