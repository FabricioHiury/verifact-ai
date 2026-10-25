import shutil
from pathlib import Path

from verifact.config import settings


def local_path(key: str) -> Path:
    root = settings().local_storage_path.resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Invalid storage key")
    return path


def check_disk(incoming: int = 0) -> None:
    cfg = settings()
    cfg.local_storage_path.mkdir(parents=True, exist_ok=True)
    used = sum(p.stat().st_size for p in cfg.local_storage_path.rglob("*") if p.is_file())
    if cfg.media_temp_dir.exists():
        used += sum(p.stat().st_size for p in cfg.media_temp_dir.rglob("*") if p.is_file())
    if used + incoming > cfg.storage_budget_mb * 1024 * 1024:
        raise ValueError("Orçamento de armazenamento atingido")
    if (
        shutil.disk_usage(cfg.local_storage_path).free - incoming
        < cfg.min_free_disk_mb * 1024 * 1024
    ):
        raise ValueError("Espaço livre insuficiente")


def publish(path: Path, key: str) -> None:
    cfg = settings()
    if cfg.storage_backend == "minio":
        from minio import Minio

        client = Minio(
            cfg.minio_endpoint,
            access_key=cfg.minio_access_key.get_secret_value(),
            secret_key=cfg.minio_secret_key.get_secret_value(),
            secure=cfg.minio_use_ssl,
        )
        if not client.bucket_exists(cfg.minio_bucket):
            client.make_bucket(cfg.minio_bucket)
        client.fput_object(cfg.minio_bucket, key, str(path))
    # Keep a bounded local working copy for subprocesses and range-serving media.
    target = local_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    if path.resolve() != target:
        shutil.copyfile(path, target)
