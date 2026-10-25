"""Pull configured models into the running Compose Ollama volume."""

import shutil
import subprocess

from verifact.config import settings

compose = ["docker", "compose"]
if subprocess.run([*compose, "version"], capture_output=True).returncode:
    binary = shutil.which("docker-compose")
    if not binary:
        raise SystemExit("Install Docker Compose first")
    compose = [binary]
config = settings()
for model in dict.fromkeys((config.ollama_model, config.ollama_fallback_model)):
    subprocess.run([*compose, "exec", "-T", "ollama", "ollama", "pull", model], check=True)
