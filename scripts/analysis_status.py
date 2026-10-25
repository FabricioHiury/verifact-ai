"""Read-only local analysis diagnostics, using the same public API as the UI."""

import sys
from pathlib import Path

import httpx
from sqlalchemy import select
from verifact.config import settings
from verifact.db import factory
from verifact.models import ResearchQuery

identifier = sys.argv[1] if len(sys.argv) > 1 else Path("data/live-analysis-id").read_text().strip()
config = settings()
base = f"http://{config.app_host}:{config.app_port}/api/v1"
with httpx.Client(timeout=10, trust_env=False) as client:
    analysis = client.get(f"{base}/analyses/{identifier}")
    analysis.raise_for_status()
    item = analysis.json()
    print("Analysis:", identifier, item["status"], item["stage"])
    if item.get("error"):
        print("Error:", item["error_code"], item["error"])
    response = client.get(f"{base}/analyses/{identifier}/claims")
    response.raise_for_status()
    for claim in response.json():
        print("Claim:", claim["statement"])
        print("Verdict:", claim["verdict"])
        queries = claim.get("research_queries")
        if queries is None:
            with factory()() as db:
                queries = [
                    {"purpose": q.purpose, "query": q.query, "outcome": q.outcome}
                    for q in db.scalars(
                        select(ResearchQuery).where(ResearchQuery.claim_id == claim["id"])
                    )
                ]
        for query in queries:
            print("Research:", query["purpose"], repr(query["query"]), query["outcome"])
        for evidence in claim["evidence"]:
            print("Evidence:", evidence["stance"], evidence["url"], repr(evidence["excerpt"]))
