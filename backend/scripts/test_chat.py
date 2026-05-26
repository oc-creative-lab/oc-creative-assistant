"""阶段 4 端到端联调脚本; 任意 shell (CMD / PowerShell / bash) 都能跑。"""

from __future__ import annotations

import json
from urllib.request import Request, urlopen


BASE = "http://127.0.0.1:9000/api"


def post(path: str, body: dict) -> dict:
    request = Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request) as response:
        return json.loads(response.read())


def get(path: str) -> dict | list:
    with urlopen(f"{BASE}{path}") as response:
        return json.loads(response.read())


def main() -> None:
    session = post("/sessions", {"project_id": "default-project", "title": "阶段 4 联调"})
    print(f"session.id = {session['id']}")

    chat = post(
        "/chat",
        {
            "session_id": session["id"],
            "user_message": "想个矮人铁匠",
            "selected_node_ids": [],
        },
    )
    print("---")
    print(f"intent          = {chat['intent']}")
    print(f"reply_text      = {chat['reply_text']}")
    print(f"batch_id        = {chat['batch_id']}")
    print(f"staging_count   = {chat['staging_count']}")
    print(f"staging_summary = {chat['staging_summary']}")
    print("---")

    staging = get(f"/sessions/{session['id']}/staging?status=pending")
    print(json.dumps(staging, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()