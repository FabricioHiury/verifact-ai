import os
import shutil
import subprocess
from pathlib import Path

from verifact.config import ROOT


def compose_command() -> list[str]:
    if shutil.which("docker-compose"):
        return ["docker-compose", "--project-directory", str(ROOT)]
    if shutil.which("docker"):
        return ["docker", "compose", "--project-directory", str(ROOT)]
    raise RuntimeError("Docker Compose necessário; execute make setup-social")


def cleanup_orphans() -> None:
    if not shutil.which("docker"):
        return
    result = subprocess.run(
        [
            "docker",
            "ps",
            "-q",
            "--filter",
            "label=com.docker.compose.project=verifact",
            "--filter",
            "label=com.docker.compose.service=downloader",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    identifiers = result.stdout.split()
    if identifiers:
        subprocess.run(
            ["docker", "rm", "-f", *identifiers], capture_output=True, timeout=15, check=True
        )


def download_command(
    output: Path, url: str, identifier: str
) -> tuple[list[str], dict[str, str], str]:
    output.mkdir(parents=True, exist_ok=True)
    name = "verifact-download-" + identifier
    command = [
        *compose_command(),
        "--profile",
        "media",
        "run",
        "--rm",
        "--no-deps",
        "-T",
        "--name",
        name,
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "downloader",
        url,
    ]
    return command, {**os.environ, "DOWNLOAD_OUTPUT_DIR": str(output.resolve())}, name
