# Validation ledger

This file records observed behavior, not planned acceptance. No representative
accuracy, neutrality or memory benchmark has been completed.

## Executed successfully

- Python dependency resolution/installation and uv lock verification; optional MLX
  and pyannote adapters installed on Apple Silicon. Node workspace installed with
  pnpm lockfile. Next.js 16.4.3 / React 19.3.1 / Python 3.12.15.
- `docker-compose up -d --wait --pull never`: PostgreSQL, Redis, SearXNG, MinIO,
  Ollama healthy, loopback ports. Official cached Ollama/MinIO images pinned by
  digest. MinIO remote registry access failed; see ADR 001 for fresh-install risk.
- `alembic upgrade head` and `alembic check`: initial relational migration applied,
  no schema drift. Real PostgreSQL isolated-schema repository test passed.
- API startup, worker solo/concurrency 1 startup and Redis connectivity observed.
- Real MP3 upload returned 202, SHA-256/media metadata persisted, MinIO reachable.
- A synthetic permission-free spoken Portuguese sample was transcribed by MLX:
  “O Brasil tem 26 estados e um distrito federal.” No voice identity was invented.
- Missing Community-1 terms/token paused at DIARIZING with an explicit error.
  Resume in explicitly degraded mode reused the transcription checkpoint.
- Real SearXNG search returned URLs; real retrieved HTML/text from IBGE:
  https://atlasescolar.ibge.gov.br/brasil/3025-federacao-e-territorio/3036-unidades-politico-administrativas.html
  This retrieval alone is not a completed claim assessment.
- `pnpm build`: passed using Next.js Webpack. Turbopack failed in this environment
  while creating a subprocess/port; scripts now use the supported Webpack option.
- `pnpm test`: 4 Vitest/React Testing Library tests passed.
- `pnpm test:e2e`: 2 Playwright tests passed; the analysis-detail test intercepts
  explicitly synthetic fixture data and is not a production fact check.
- Ruff, mypy and frontend ESLint/type checks passed in the checks run so far.
- 43 Python tests passed before the latest added tests; five additional focused
  job/CrewAI tests passed separately. Final consolidated counts to be recorded.
- WeasyPrint rendered a 6052-byte synthetic PDF with a citation link using
  DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib. This is renderer validation, not
  evidence that a full analysis PDF has been generated.

## Resource observations and external prerequisites

A 2 GB Colima VM killed the Qwen3 1.7B runner during load. The maintainer authorized
restarting it with 4 GB; Docker reports 4096626688 available bytes. Both qwen3:4b
and qwen3:1.7b are downloaded into the Ollama volume. Full live verification with
4 GB is still being tested; no successful result is assumed.

Community-1 requires the user's own accepted terms and read token. No token was
invented. Tests used DIARIZATION_ENABLED=false explicitly for later stages. The
normal .env keeps diarization enabled. Social download remains blocked until an
outbound sandbox covers downloader subrequests. Source PDF extraction, cross-chunk
speaker reconciliation and representative long-media profiling remain incomplete.

## Distinctions

Unit/evaluation fixtures and mocked HTTP transports are synthetic. A CrewAI contract
test executes the real framework against mocked local HTTP responses; it validates
integration contracts, not inference quality. Live web retrieval and live media
transcription above used actual services. No complete factual verdict or report is
claimed until the live pipeline finishes and references are checked.
