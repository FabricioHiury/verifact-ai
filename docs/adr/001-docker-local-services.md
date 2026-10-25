# ADR 001: Docker-managed local infrastructure and inference

Status: accepted following the user's explicit request to run Ollama, MinIO and
other local services in Docker. This supersedes earlier native-Ollama guidance.

PostgreSQL, Redis, SearXNG, MinIO and Ollama run in Compose by default, with named
volumes, health checks and loopback-only published ports. The API and worker still
run on the host and use localhost port mappings. MinIO is the default object
backend; filesystem remains an explicit lighter alternative.

Ollama runs CPU-only in the Linux VM on macOS; Metal acceleration is unavailable
there. This is a deliberate operational tradeoff, not a performance improvement.
MLX stays native because macOS Metal is required. A Linux transcription worker
would require the portable faster-whisper adapter instead; it is not an equivalent
MLX container. No cloud inference is enabled. Only one model and one request are
allowed; idle model residency is zero. Models persist in a volume but loading is
separate from downloading. No model is bundled in the image.

Container limits are initial ceilings, not guarantees. The Docker VM and native
media subprocesses share the machine's 8 GB. Do not raise VM allocation blindly;
measure pressure/swap and reduce model or service use if necessary. Start with the
fallback model for diagnosis if Qwen3 4B does not fit. Native Ollama could restore
Metal later only if the user explicitly changes this decision.

References: https://docs.ollama.com/docker and https://docs.ollama.com/faq.

## Registry availability observed during setup

The requested MinIO Docker Hub release and Quay pull failed (access denied). An
official arm64 MinIO RELEASE.2025-09-07T16-13-09Z image already cached locally was
verified with `--version` and pinned by repository digest. Ollama 0.40.0 was also
available locally and pinned by digest. A fresh machine may need to obtain/build
MinIO from its verified source if that digest is unavailable. The upstream MinIO
repository is archived; review security maintenance before any non-local use.
Reference: https://github.com/minio/minio.
