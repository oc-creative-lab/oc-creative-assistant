import argparse

import uvicorn

from main import app


# PyInstaller 打包后的后端入口也走这套参数，Electron 主进程会传入 host/port。
def parse_args() -> argparse.Namespace:
    """解析后端启动参数；只读取命令行，不启动服务。"""
    parser = argparse.ArgumentParser(description="Run the OC Creative Assistant backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    return parser.parse_args()


def main() -> None:
    """命令行入口；按参数启动 uvicorn 服务，不直接处理业务请求。"""
    args = parse_args()
    # 桌面应用由 Electron 管理进程生命周期，打包态不启用 reload。
    uvicorn.run(app, host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
