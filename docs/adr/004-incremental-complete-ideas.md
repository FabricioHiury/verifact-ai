# 004 — Incremental research after complete speech ideas

The maintainer requested enabled Community-1 diarization and research that waits
for the speaker's complete idea rather than isolated Whisper fragments.

The deterministic CrewAI Flow now alternates transcription, diarization,
idea extraction and pending-claim verification for each persisted audio chunk.
All heavyweight operations remain sequential. A chunk boundary does not imply
the end of an idea: an unfinished tail is reread from persisted transcript on the
next chunk, and the last sentence waits for lookahead unless media has ended.

Punctuation or a pause of at least 1.5 seconds proposes boundaries; known correction/qualification connectors retain
the continuation. A structured local-model response must additionally declare
the idea complete before any claims are admitted to research. An incomplete
response is accumulated with subsequent segments. Speaker changes and end of
media close the available passage but do not override semantic incompleteness.
An idea exceeding the 4000-character context window is skipped through its next
boundary, with a limitation, rather than researched as arbitrarily sliced text.

Original passages are preserved. Claim quotes must be exact substrings of the
space-joined original segments. Start and end segment foreign keys preserve
original timestamps; the API and HTML/PDF include the full context. Quotations
spanning distinct or uncertain voice labels are withheld for human review.
Chunk-local labels are not automatically reconciled into identities.

Each consumed passage has a transactional IDEAS checkpoint alongside claims.
Research/verdict checkpoints remain per claim. Pending tails survive restart
without holding a model or an entire transcript in memory. Model/prompt/pipeline
versions prevent silent reuse of incompatible previous analyses; create a new
analysis when an existing checkpoint is incompatible. Historical reports remain
historical and are not silently upgraded.

Semantic completion is a model-assisted heuristic, not a guarantee of complete
political context or improved accuracy. No faster-tempo audio or concurrent
heavyweight inference is introduced. The alternative of concurrent Whisper and
Qwen would violate the 8 GB resource policy; whole-media-only verification delays
all results unnecessarily and does not address fragmented claim extraction.
