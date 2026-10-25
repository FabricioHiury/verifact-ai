# ADR 002: Local-only inference despite CrewAI transitive SDK dependencies

Status: accepted conservative compatibility decision.

CrewAI 1.15.30 is installed and locked. It requires `crewai-core` and transitively
installs the OpenAI SDK and other provider-related packages. The requirement to
use current CrewAI conflicts with a literal ban on even transitive cloud SDK
packages. Do not remove required dependencies behind the resolver's back.

Application inference uses only LocalOllama, a CrewAI BaseLLM subclass calling the
loopback Ollama chat API. No cloud SDK is imported by application inference code,
no cloud API key is configured, memory and tracing are disabled, and CrewAI/OTel
telemetry is disabled before framework imports. Ollama cloud features are disabled
in Compose. No cloud fallback is allowed. This does not assert that upstream
packages contain no provider code. Audit transitive dependencies before release.

CrewAI custom adapter reference: https://docs.crewai.com/en/learn/custom-llm.
