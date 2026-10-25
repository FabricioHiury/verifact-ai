from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from verifact.models import Analysis, ProcessingCheckpoint, Status
from verifact_worker.media import PrerequisiteError
from verifact_worker.pipeline import Cancelled, Pipeline


def test_chunk_checkpoint_resume_and_configuration_change(database):
    item = Analysis(title="Fixture de recuperação", status=Status.RUNNING)
    database.add(item)
    database.commit()
    maker = sessionmaker(database.get_bind(), expire_on_commit=False)
    with patch("verifact_worker.pipeline.factory", return_value=maker):
        flow = Pipeline(item.id, 0)
        assert not flow.done("TRANSCRIBING", "0")
        flow.save_checkpoint(database, "TRANSCRIBING", "0")
        database.commit()
        assert flow.done("TRANSCRIBING", "0")
        # A missing diarization prerequisite can be disabled without invalidating transcription.
        flow.identities["diarization_enabled"] = False
        assert flow.done("TRANSCRIBING", "0")
        assert database.scalar(select(ProcessingCheckpoint)) is not None
        flow.identities["whisper_model"] = "different-model"
        with pytest.raises(PrerequisiteError):
            flow.done("TRANSCRIBING", "0")


def test_cancel_is_read_from_durable_state(database):
    item = Analysis(title="Fixture cancelamento", status=Status.CANCEL_REQUESTED)
    database.add(item)
    database.commit()
    maker = sessionmaker(database.get_bind(), expire_on_commit=False)
    with patch("verifact_worker.pipeline.factory", return_value=maker):
        with pytest.raises(Cancelled):
            Pipeline(item.id, 0).check_cancel()
