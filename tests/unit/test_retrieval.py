from unittest.mock import patch

import pytest
from verifact.security import Document
from verifact_worker.reports import deny_resource
from verifact_worker.research import retrieve


def test_retrieve_uses_real_document_not_search_snippet():
    # Synthetic untrusted source fixture, deliberately not a real analysis.
    html = (
        b"<html><title>Fixture</title><script>steal()</script><body>"
        + b"Public data excerpt. " * 20
        + b"</body></html>"
    )
    responses = [
        Document("https://example.org/robots.txt", b"User-agent: *\nAllow: /", "text/plain"),
        Document("https://example.org/data", html, "text/html"),
    ]
    with patch("verifact_worker.research.fetch_public", side_effect=responses):
        source = retrieve("https://example.org/data")
    assert "Public data excerpt" in source.text
    assert "steal()" not in source.text
    assert source.publication_date is None
    assert len(source.content_hash) == 64


def test_robots_restrictions_are_enforced():
    robots = Document("https://example.org/robots.txt", b"User-agent: *\nDisallow: /", "text/plain")
    with patch("verifact_worker.research.fetch_public", return_value=robots):
        with pytest.raises(ValueError, match="robots"):
            retrieve("https://example.org/private")


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "http://169.254.169.254/", "https://example.org/image.png"]
)
def test_pdf_cannot_fetch_external_resources(url):
    with pytest.raises(ValueError):
        deny_resource(url)


def test_query_cannot_promote_invented_url_to_source():
    from verifact_worker.research import query_text

    actual = query_text(
        "https://www.ibge.gov.br/invented-endpoint", "Afirmação original", "falsifying"
    )
    assert "http" not in actual
    assert "divergentes" in actual
    assert "site:ibge.gov.br" in query_text(
        "população site:ibge.gov.br", "Afirmação", "primary_source"
    )


def test_retrieval_window_finds_body_after_navigation():
    from verifact_worker.research import relevant_window

    text = "Brasil navegação " + "menu " * 500 + "O Brasil tem 26 estados e um Distrito Federal."
    window = relevant_window(text, "O Brasil tem 26 estados e um Distrito Federal.")
    assert "26 estados" in window
    assert window in text


def test_site_only_query_keeps_original_claim_context():
    from verifact_worker.research import query_text

    query = query_text(
        "site:ibge.gov.br", "O Brasil tem 26 estados e um Distrito Federal.", "primary_source"
    )
    assert "26 estados" in query and "site:ibge.gov.br" in query
