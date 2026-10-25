# Docker-managed local services

`make infra-up` starts PostgreSQL, Redis, SearXNG, MinIO and Ollama, waiting for
health checks. `make models-pull` downloads configured Qwen3 models into the Ollama
volume; the application still needs models after a healthy server starts.
`make infra-down` stops containers without deleting volumes.

Host API/worker use localhost:5432, :6379, :8080, :9000 and :11434. MinIO console
is localhost:9001. Credentials live only in the ignored root .env. No service is
published to the LAN. API/web/worker run natively with `make dev`; MLX requires
macOS Metal and therefore remains native.

Ollama in Docker on macOS uses CPU rather than Metal. Limits are one loaded model,
one inference request, 4096 initial context and immediate unloading. Container
memory ceilings exclude Docker VM overhead; inspect `docker stats`, Activity
Monitor memory pressure and `vm_stat`. Never assume the combined application fits
8 GB merely because individual containers are capped. See ADR 001.

Filesystem remains available via STORAGE_BACKEND=filesystem, but MinIO starts by
default as requested. Containerizing application processes later requires explicit
service-name URLs instead of host localhost mappings.
