# ADR 003: Network sandbox for optional public social retrieval

A generic host yt-dlp adapter cannot guarantee SSRF protection for redirects,
manifest fragments and secondary requests. Use an on-demand downloader container
on a dedicated internal Docker network. It has no direct public egress and no
connection to the application's database/storage network. Only a CONNECT proxy
joins that internal network and an egress network. The proxy resolves every new
connection, rejects all non-public addresses/ports, and pins the validated IP.
TLS hostname/certificate verification remains with yt-dlp. HTTP origins are denied.

The utility container has a read-only root, dropped capabilities, no Docker socket,
no credentials, bounded temporary memory and one output directory. It cannot use
host cookies or credentials. yt-dlp runs native retrieval only; FFmpeg is used only
for local media conversion with file/pipe protocols. Private/login/DRM failures
remain failures. Permission must be confirmed before submission. Platform anti-bot
restrictions and missing JavaScript support may still prevent retrieval.

This is a security utility, not a new application microservice. The host worker
starts the proxy/utility via Compose within the existing global heavy-operation
lock. No downloader port is published to the host. Network restrictions must be
validated against Docker before marking downloads operational. Public access is
not proof of permission to redistribute.
