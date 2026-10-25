"""Create local credentials without printing or overwriting them."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if not target.exists():
    content = (root / ".env.example").read_text()
    content = content.replace("replace-with-random-local-password", secrets.token_hex(24))
    content = content.replace("replace-with-random-local-key", secrets.token_hex(32))
    content = content.replace("replace-with-random-minio-password", secrets.token_hex(24))
    content = content.replace("MINIO_ACCESS_KEY=\n", "MINIO_ACCESS_KEY=verifact-local\n")
    content = content.replace(
        "MINIO_SECRET_KEY=\n", "MINIO_SECRET_KEY=" + secrets.token_hex(24) + "\n"
    )
    target.write_text(content)
    target.chmod(0o600)
    print("Created ignored local .env; external tokens remain empty.")
else:
    print("Preserved existing .env.")
