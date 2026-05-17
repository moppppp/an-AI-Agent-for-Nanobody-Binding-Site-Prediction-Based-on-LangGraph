"""Start the nanobody agent web UI."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    print(
        "启动 Web 服务。首次会在后台加载向量模型与知识库，终端会打印进度；"
        "页面显示「就绪」后即可提问。退出请按 Ctrl+C。\n",
        flush=True,
    )
    for script in ("gen_web_static.py", "extract_css.py"):
        path = ROOT / "scripts" / script
        if path.is_file():
            subprocess.run([sys.executable, str(path)], cwd=str(ROOT), check=False)
            break
    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "web.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
            "--app-dir",
            str(ROOT),
        ],
        cwd=str(ROOT),
        check=True,
    )


if __name__ == "__main__":
    main()
