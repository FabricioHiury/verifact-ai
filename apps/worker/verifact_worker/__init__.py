"""Sequential local processing worker."""

import logging
import os

from verifact.config import ROOT

os.environ["CREWAI_STORAGE_DIR"] = str(ROOT / "data/crewai")
os.environ["CREWAI_TELEMETRY_DISABLED"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

logging.getLogger("httpx").setLevel(logging.WARNING)
