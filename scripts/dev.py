"""Run native services with the root environment and cleanup their process groups."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
env = {**{k: v for k, v in dotenv_values(root / ".env").items() if v is not None}, **os.environ}
if sys.platform == "darwin" and Path("/opt/homebrew/lib").is_dir():
    env.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")
commands = {
    "api": [
        str(root / ".venv/bin/uvicorn"),
        "verifact.api:app",
        "--host",
        env.get("APP_HOST", "127.0.0.1"),
        "--port",
        env.get("APP_PORT", "8000"),
        "--log-level",
        env.get("LOG_LEVEL", "INFO").lower(),
    ],
    "worker": [
        str(root / ".venv/bin/celery"),
        "-A",
        "verifact_worker.celery_app:app",
        "worker",
        "--pool=solo",
        "--concurrency=1",
        "--beat",
        "--schedule",
        str(root / "data/celerybeat"),
        "--loglevel",
        env.get("LOG_LEVEL", "INFO"),
    ],
    "web": ["pnpm", "--filter", "@verifact/web", "dev", "--port", env.get("WEB_PORT", "3000")],
}
(root / "data").mkdir(exist_ok=True)
selected = sys.argv[1:] or list(commands)
if any(name not in commands for name in selected):
    raise SystemExit("Use api, worker, web, or no argument for all services")


def terminate(signum: int, frame: object) -> None:
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, terminate)
processes = []
try:
    for name in selected:
        processes.append(
            subprocess.Popen(commands[name], cwd=root, env=env, start_new_session=True)
        )
    while all(p.poll() is None for p in processes):
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
if any(p.returncode not in (0, -signal.SIGTERM, -signal.SIGINT) for p in processes):
    raise SystemExit(1)
