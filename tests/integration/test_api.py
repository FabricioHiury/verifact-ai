from verifact.models import Analysis, Speaker, Status


def test_health_and_empty_history(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/v1/analyses").json() == {"items": [], "total": 0}


def test_reject_unpermitted_and_unsafe_urls(client):
    assert (
        client.post(
            "/api/v1/analyses/from-url", json={"url": "https://youtu.be/a", "permitted": False}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/analyses/from-url", json={"url": "http://127.0.0.1", "permitted": True}
        ).status_code
        == 422
    )


def test_url_submission_is_pending_not_fake_success(client, database):
    response = client.post(
        "/api/v1/analyses/from-url", json={"url": "https://youtu.be/a", "permitted": True}
    )
    assert response.status_code == 202
    item = response.json()
    assert response.headers["location"] == f"/api/v1/analyses/{item['id']}/status"
    assert item["status"] == "QUEUED"
    assert client.get(f"/api/v1/analyses/{item['id']}/claims").json() == []
    assert client.get(f"/api/v1/analyses/{item['id']}/report.pdf").status_code == 409


def test_cancel_resume_and_relationship_validation(client, database):
    item = Analysis(title="Teste", status=Status.RUNNING)
    other = Analysis(title="Outro")
    database.add_all([item, other])
    database.commit()
    assert client.post(f"/api/v1/analyses/{item.id}/resume").status_code == 409
    assert client.post(f"/api/v1/analyses/{item.id}/cancel").json()["status"] == "CANCEL_REQUESTED"
    item.status = Status.CANCELLED
    database.commit()
    assert client.post(f"/api/v1/analyses/{item.id}/resume").json()["status"] == "QUEUED"
    speaker = Speaker(analysis_id=other.id, cluster="VOICE")
    database.add(speaker)
    database.commit()
    assert (
        client.patch(
            f"/api/v1/analyses/{item.id}/speakers/{speaker.id}", json={"name": "Nome"}
        ).status_code
        == 404
    )


def test_corrections_preserve_automated_name_and_invalidate_report(client, database):
    item = Analysis(title="Teste", status=Status.COMPLETED)
    database.add(item)
    database.flush()
    speaker = Speaker(analysis_id=item.id, cluster="chunk-0:SPEAKER_00")
    database.add(speaker)
    database.commit()
    response = client.patch(
        f"/api/v1/analyses/{item.id}/speakers/{speaker.id}", json={"name": "Nome manual"}
    )
    assert response.json()["cluster"] == "chunk-0:SPEAKER_00"
    assert response.json()["manual_name"] == "Nome manual"
    assert database.get(Analysis, item.id).revision == 2
    repeat = client.patch(
        f"/api/v1/analyses/{item.id}/speakers/{speaker.id}", json={"name": "Nome manual"}
    )
    assert repeat.status_code == 200
    assert database.get(Analysis, item.id).revision == 2


def test_upload_rejects_disguised_content(client):
    response = client.post(
        "/api/v1/analyses/uploads", files={"file": ("fake.mp4", b"<html>fake</html>", "video/mp4")}
    )
    assert response.status_code == 422


def test_foreign_browser_origin_rejected(client):
    assert (
        client.post(
            "/api/v1/analyses/from-url",
            headers={"Origin": "https://evil.test"},
            json={"url": "https://youtu.be/a", "permitted": True},
        ).status_code
        == 403
    )


def test_upload_checks_disk_before_parsing_media(client, monkeypatch):
    from unittest.mock import Mock

    monkeypatch.setattr("verifact.api.check_disk", Mock(side_effect=ValueError("disk budget")))
    response = client.post(
        "/api/v1/analyses/uploads", files={"file": ("sample.mp3", b"ID3test", "audio/mpeg")}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "STORAGE_BUDGET"


def test_retrieved_source_is_visible_without_claiming_support(client, database):
    from verifact.models import Claim, ResearchQuery, Source, TranscriptSegment

    item = Analysis(title="Synthetic provenance fixture")
    database.add(item)
    database.flush()
    segment = TranscriptSegment(
        analysis_id=item.id,
        chunk=0,
        ordinal=0,
        start_time=0,
        end_time=1,
        text="Trecho sintético.",
        model="fixture",
    )
    database.add(segment)
    database.flush()
    claim = Claim(
        analysis_id=item.id,
        segment_id=segment.id,
        statement=segment.text,
        context="Fixture",
        checkable=True,
    )
    database.add(claim)
    database.flush()
    query = ResearchQuery(
        claim_id=claim.id,
        query="synthetic fixture",
        purpose="primary_source",
        outcome="Fixture: documento recuperado sem apoio confirmado",
    )
    database.add(query)
    database.flush()
    database.add(
        Source(
            query_id=query.id,
            url="https://example.org/synthetic",
            title="Synthetic fixture only",
            publisher="example.org",
            publication_date=None,
            source_type="TEST_FIXTURE",
            content_hash="a" * 64,
            excerpt="Conteúdo sintético para teste de proveniência.",
        )
    )
    database.commit()
    response = client.get(f"/api/v1/claims/{claim.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence"] == []
    assert payload["research_queries"][0]["sources"][0]["title"] == "Synthetic fixture only"
