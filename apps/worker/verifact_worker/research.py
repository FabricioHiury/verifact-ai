import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup, Tag
from verifact.config import settings
from verifact.security import fetch_public

PRIMARY = {
    "ibge.gov.br",
    "tse.jus.br",
    "bcb.gov.br",
    "tesourotransparente.gov.br",
    "camara.leg.br",
    "senado.leg.br",
    "portaldatransparencia.gov.br",
}


@dataclass
class Retrieved:
    url: str
    title: str
    publisher: str
    publication_date: str | None
    source_type: str
    content_hash: str
    text: str


def retrieve(url: str) -> Retrieved:
    cfg = settings()
    parsed = urlsplit(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        robots = fetch_public(robots_url, timeout=cfg.search_request_timeout, max_bytes=100_000)
        rules = RobotFileParser()
        rules.parse(robots.content.decode("utf-8", errors="replace").splitlines())
        if not rules.can_fetch("VerifactAI", url):
            raise ValueError("Acesso não permitido por robots.txt")
    except OSError as exc:
        # A missing robots file is common; access denial/rate limiting is not permission.
        if "HTTP 404" not in str(exc):
            raise
    document = fetch_public(url, timeout=cfg.search_request_timeout, max_bytes=cfg.source_max_bytes)
    if "text/html" not in document.content_type and "text/plain" not in document.content_type:
        raise ValueError("Formato de fonte não suportado; HTML/texto necessários")
    soup = BeautifulSoup(document.content, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else document.url
    date = soup.find("meta", attrs={"property": "article:published_time"})
    publication = (
        str(date.get("content")) if isinstance(date, Tag) and date.get("content") else None
    )
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ", strip=True).split())
    if len(text) < 80:
        raise ValueError("Documento sem conteúdo suficiente")
    host = urlsplit(document.url).hostname or "unknown"
    primary = any(host == p or host.endswith("." + p) for p in PRIMARY)
    return Retrieved(
        document.url,
        title[:500],
        host,
        publication,
        "INSTITUTIONAL" if primary else "SECONDARY_OR_UNKNOWN",
        hashlib.sha256(document.content).hexdigest(),
        text,
    )


def search(query: str) -> list[str]:
    cfg = settings()
    with httpx.Client(timeout=cfg.search_request_timeout, trust_env=False) as client:
        response = client.get(
            cfg.searxng_base_url + "/search",
            params={
                "q": query,
                "format": "json",
                "engines": cfg.search_engine,
                "language": cfg.search_language,
            },
        )
        response.raise_for_status()
        results = response.json().get("results", [])
    return list(dict.fromkeys(str(item["url"]) for item in results if item.get("url")))[
        : cfg.search_max_results
    ]


def retrieve_results(urls: list[str]) -> list[Retrieved | Exception]:
    def attempt(url: str) -> Retrieved | Exception:
        try:
            return retrieve(url)
        except Exception as exc:
            return exc

    with ThreadPoolExecutor(max_workers=settings().search_max_concurrent_requests) as pool:
        return list(pool.map(attempt, urls))


def relevant_window(text: str, statement: str, max_chars: int = 1800) -> str:
    # Score bounded real-text windows so navigation mentions do not hide the actual passage.
    tokens = {w.lower().strip(".,;:!?") for w in statement.split() if len(w) > 3}
    best_start, best_score = 0, -1
    for start in range(0, len(text), max_chars // 2):
        window = text[start : start + max_chars].lower()
        score = sum(window.count(token) for token in tokens)
        if score > best_score:
            best_start, best_score = start, score
    return text[best_start : best_start + max_chars]


def query_text(query: str, statement: str, purpose: str) -> str:
    # A model-suggested URL is not a verified endpoint or document reference.
    if "http://" in query.lower() or "https://" in query.lower():
        query = "site:gov.br" if purpose == "primary_source" else ""
    terms = {word.lower().strip(".,;:!?") for word in statement.split() if len(word) > 3}
    if sum(term in query.lower() for term in terms) < min(2, len(terms)):
        query = statement[:140] + " " + query[:55]
    if purpose == "falsifying" and not any(
        word in query.lower() for word in ("contradi", "refut", "diverg", "falso")
    ):
        query = query[:170] + " dados divergentes"
    return query.strip()[:200]
