# Implementation plan

## Authority and compatibility

The full implementation request supersedes the earlier documentation-only restriction in AGENTS.md. Keep the existing vision and both README translations. Use Python 3.12 for CrewAI/media compatibility, Node 24, pnpm 10, native macOS API/worker/MLX, and Compose infrastructure including Ollama and MinIO per ADR 001. Verify installed APIs rather than guessing model/library compatibility.

## Milestones and acceptance

1. Foundation: typed configuration, ignored random local credentials, workspace and locks, normalized relational entities, Alembic, API/worker, generated contracts, Compose, startup commands. Acceptance: migrations, API health, web build and database integration checks.
2. Media: bounded upload, hashes, ffprobe, chunked isolated transcription, diarization with explicit missing-token behavior, progress/checkpoints/cancel/resume. Acceptance: generated permission-free audio ingestion and boundary/recovery tests; live models separately identified.
3. Verification: deterministic CrewAI Flow, seven sequential agents, custom local Ollama transport, bounded research, actual document retrieval and provenance, validated verdicts. Acceptance: deterministic fixtures and opt-in live claim evaluation; never replace retrieval failures with fixtures.
4. Interface/reports: dashboard/upload/details/reports, media streaming, manual corrections, timestamp navigation, citations and Jinja2/WeasyPrint exports. Acceptance: web checks, browser workflows and PDF generation.
5. Reliability: security, retry/idempotency tests, CI, profiling and operational docs. Acceptance: relevant checks executed and exact unresolved prerequisites disclosed.

## Decisions

- PostgreSQL session advisory lock across each job enforces one analysis/heavy operation installation-wide, without expiring leases during inference. Host file lock guards against orphan heavy children after worker death. Queued jobs remain durable and can be redispatched.
- Durable stage/chunk checkpoints, bounded transcript batches and per-claim transactions. Redis is transport only. Stage status is distinct from terminal analysis state; add PARTIALLY_COMPLETED for explicit degraded output.
- Inference adapters are optional dependency groups to avoid installing Torch/MLX for ordinary CI. CrewAI uses a custom BaseLLM through Ollama HTTP, not cloud SDK inference.
- Public social retrieval is an opt-in Docker utility with an internal-only network and pinned public CONNECT proxy (ADR 003). Network policy is tested; platform retrieval remains best-effort and must fail honestly when restricted.
- Unknown speaker labels remain unknown. Missing HF access pauses by default; explicitly disable diarization to accept degraded output. Chunk-local diarization labels are not reconciled identities.

## Dependencies and risks

Docker daemon access, network package downloads, Docker Ollama models, native PDF libraries, and gated Community-1 weights may require external setup. Quantized small models can still exceed available RAM alongside Docker. Search engines can block queries. Retrieved HTML may be incomplete; PDF extraction and authenticated sites are not assumed. Review output quality manually. License remains undecided; no release license is implied.

## Verification ledger

Populate docs/VALIDATION.md with actual executed checks, blockers and live versus mocked distinctions. A milestone is not complete solely because its modules exist.
