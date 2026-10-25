import httpx
from redis import Redis
from sqlalchemy import text
from verifact.config import settings
from verifact.db import engine

cfg = settings()
with engine().connect() as connection:
    connection.execute(text("SELECT 1"))
print("PostgreSQL: ok")
assert Redis.from_url(cfg.celery_broker_url.get_secret_value()).ping()
print("Redis: ok")
services = [
    ("API", f"http://{cfg.app_host}:{cfg.app_port}/health"),
    ("SearXNG", cfg.searxng_base_url + "/healthz"),
    ("Ollama server (not model readiness)", cfg.ollama_base_url + "/api/tags"),
]
if cfg.storage_backend == "minio":
    protocol = "https" if cfg.minio_use_ssl else "http"
    services.append(("MinIO", f"{protocol}://{cfg.minio_endpoint}/minio/health/live"))
failed = False
for name, url in services:
    try:
        response = httpx.get(url, timeout=5, trust_env=False)
        response.raise_for_status()
        print(name + ": ok")
    except httpx.HTTPError:
        print(name + ": unavailable")
        failed = True
if failed:
    raise SystemExit(1)
