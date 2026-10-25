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
normal .env keeps diarization enabled. Social downloads use an isolated Docker network and a public-address CONNECT
proxy; the current installation explicitly enables the adapter. Source PDF extraction, cross-chunk
speaker reconciliation and representative long-media profiling remain incomplete.

## Distinctions

Unit/evaluation fixtures and mocked HTTP transports are synthetic. A CrewAI contract
test executes the real framework against mocked local HTTP responses; it validates
integration contracts, not inference quality. Live web retrieval and live media
transcription above used actual services. No complete factual verdict or report is
claimed until the live pipeline finishes and references are checked.

## YouTube adapter validation — 2026-10-25

- Rebuilt the downloader with official Node.js 24 (digest pinned in Dockerfile),
  yt-dlp 2026.10.21 with its default/EJS dependencies, and no remote-component
  downloads. Container smoke checks observed Node v24.22.1 and the EJS import.
- Enabled SOCIAL_DOWNLOAD_ENABLED in the ignored local .env and restarted the
  API/solo worker. Fresh installations retain the explicit opt-in setting.
- Downloaded Blender's public Big Buck Bunny through the protected proxy:
  https://www.youtube.com/watch?v=aqz-KE-bpKQ
  Normalization completed: MP3, 634.656 seconds, 13,372,992 bytes, SHA-256 recorded.
  This is real retrieval/normalization, not a factual analysis or validation of
  full transcription through the URL submission pipeline.
- Updated the public-link form and verified Playwright: 2 passed, 1 opt-in live
  analysis test skipped. Python suite: 68 passed, 1 opt-in PostgreSQL test skipped;
  CrewAI emitted 13 upstream deprecation warnings. Frontend typecheck and lint
  passed. Tests explicitly disable live downloads instead of inheriting .env.
- Added regression coverage for local JavaScript runtime configuration, no
  remote components, bounded download concurrency, proxy routing, and no cookies.
  Cancellation admission now prevents an additional inference after cancellation.
- Long-media behavior remains sequential by stage, with persisted transcript
  chunks. No concurrent Whisper/Qwen or accelerated-tempo mode was introduced.
  No two-hour transcription benchmark or speed/accuracy equivalence is claimed.


## Enabled diarization and incremental complete ideas — 2026-10-25

- The maintainer configured their own Hugging Face token locally. No token was
  printed or committed. The worker now starts from .env with diarization enabled,
  without the previous DIARIZATION_ENABLED=false override.
- Community-1 downloaded and executed locally on the permission-free short
  Portuguese speech sample: exit 0, one speech turn and one voice cluster.
  This proves access and local inference, not multi-speaker accuracy.
- Applied additive migration 20261025_idea_spans; alembic check reported no drift.
  The opt-in real PostgreSQL isolated-schema test passed.
- Implemented alternating chunk stages under the real CrewAI Flow, structured
  complete-idea admission, durable pending tails, original context and quote spans.
  Synthetic tests cover incomplete sentences across chunks/restart, semantic
  rejection, correction connectors, oversized passages, mixed-voice quotes,
  idempotent checkpoints, API timestamp spans and sequential stage ordering.
- The first integrated live run transcribed and diarized successfully, then the
  model incorrectly marked the factual sample uncheckable and produced an invalid
  citation during judgment. Validation rejected it; no successful result was
  fabricated. The extraction instructions were clarified and non-checkable claims
  now use an explicitly deterministic no-evidence result without factual research.
- A second live run with pt-br-v5-ideas admitted the factual claim and reached
  real source retrieval, but an invented/nonliteral excerpt was rejected. The
  worker now records that rejection and continues other sources; if no admissible
  evidence remains, it records an explicitly deterministic INCONCLUSIVE result.
  No invented quote becomes evidence. The same sample was resumed from media and
  idea checkpoints to exercise recovery; its final outcome is recorded separately.
- No representative two-hour benchmark, multi-speaker accuracy evaluation, or
  measured improvement in factual precision has been completed. Completion remains
  a model-assisted heuristic. Previous incompatible checkpoints require a new
  analysis rather than silently replacing historical results.

- Consolidated checks after the recovery and chunk-continuity fixes: 78 Python tests passed, one opt-in
  PostgreSQL test skipped in that suite; the real PostgreSQL test passed separately.
  Ruff and mypy passed. Frontend typecheck/lint and four Vitest tests passed.
  Two standard Playwright tests passed, with the opt-in live test skipped; these
  include opening the preserved original speech context. Upstream CrewAI emitted
  13 deprecation warnings. No hosted inference was used.

- An opt-in browser run against the historical real analysis
  954fc902-1241-4df0-962f-321e888a5430 passed all three Playwright tests, including
  real source-link visibility and PDF magic bytes. The initial run found an
  ambiguous text locator (the quote legitimately appeared twice); the locator
  was scoped to the transcript panel and the rerun passed. This checks backward
  compatibility, not the outcome of the new live sample.
- Chunk-local voice labels no longer imply a speaker change across chunk
  boundaries. Context is retained, while quotes spanning distinct/uncertain voice
  labels are withheld. Punctuation and pauses only nominate a boundary; the
  local model must still accept semantic completion. Focused idea tests cover
  these cases without presenting synthetic transcripts as real analyses.


### Final outcome of the resumed diarized sample

Analysis e2a32cc9-56b9-48ea-ac4d-26b6a4917c96 reached PARTIALLY_COMPLETED with
prompt pt-br-v5-ideas. Its single factual claim retained the original full speech
context and a real Community-1 cluster. Three query purposes ran against live
search and retrieved source documents. No proposed excerpt passed literal
validation, so no Evidence row was fabricated. The verdict is explicitly
INCONCLUSIVE with model metadata deterministic:insufficient-evidence-v1.

Real API checks confirmed the cluster, preserved transcript context, HTML report
with the inconclusive result, and a 17,340-byte PDF beginning with %PDF-. The
worker was restarted after completion to load the final pause/boundary and
cross-chunk-label handling. Diarization remains enabled from the ignored .env.
These observations do not establish speaker accuracy on multiple voices or that
the model consistently selects useful evidence; the false-negative risk remains.
