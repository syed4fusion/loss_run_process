from __future__ import annotations

import asyncio
from pathlib import Path
from time import monotonic
import uuid

from app.pipeline.nodes import analytics as analytics_module
from app.pipeline.nodes import extract as extract_module
from app.pipeline.nodes.ingest import _pdf_validation_error
from app.services.gemini_client import GeminiClient


def _write_temp_pdf_like_file(filename_prefix: str, payload: bytes) -> Path:
    base = Path(__file__).resolve().parents[2] / ".test_tmp"
    base.mkdir(exist_ok=True)
    p = base / f"{filename_prefix}_{uuid.uuid4().hex}.pdf"
    p.write_bytes(payload)
    return p


def test_ingest_rejects_non_pdf_magic():
    p = _write_temp_pdf_like_file("not_pdf", b"NOTPDF content")
    try:
        err = _pdf_validation_error(str(p))
        assert err is not None
        assert "bad magic bytes" in err
    finally:
        p.unlink(missing_ok=True)


def test_ingest_rejects_encrypted_pdf_marker():
    p = _write_temp_pdf_like_file(
        "encrypted",
        b"%PDF-1.7\n1 0 obj\n<< /Encrypt 2 0 R >>\nendobj\n",
    )
    try:
        err = _pdf_validation_error(str(p))
        assert err is not None
        assert "encrypted" in err
    finally:
        p.unlink(missing_ok=True)


def test_analytics_node_graceful_failure(monkeypatch):
    class _FakeJob:
        status = None
        current_stage = None
        error_message = None

    class _FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return _FakeJob()

    class _FakeSession:
        def query(self, *args, **kwargs):
            return _FakeQuery()

        def commit(self):
            return None

        def close(self):
            return None

    def _boom(*args, **kwargs):
        raise RuntimeError("forced analytics error")

    monkeypatch.setattr(analytics_module, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(analytics_module.pd, "DataFrame", _boom)

    result = analytics_module.analytics_node(
        {
            "job_id": "job-analytics-fail",
            "claims_array": {"policy_periods": [{"period": "2024-01-01/2025-01-01", "claims": [{}]}]},
            "errors": [],
        }
    )
    assert result["current_stage"] == "analytics_failed"
    assert any("Analytics failed" in msg for msg in result["errors"])


def test_extract_claims_stores_raw_on_malformed_json(monkeypatch):
    class _Resp:
        def __init__(self, text: str):
            self.text = text
            self.parsed = None

    client = GeminiClient(api_key="dummy-key", model="dummy-model")
    client._mock_mode = False

    calls = {"count": 0}

    async def _fake_generate_structured_response(*, contents, response_schema):
        calls["count"] += 1
        return _Resp('{"broken_json":')

    monkeypatch.setattr(client, "_generate_structured_response", _fake_generate_structured_response)

    result = asyncio.run(
        client.extract_claims(
            file_ref={"name": "fake"},
            prompt="extract",
            response_schema={},
        )
    )

    assert calls["count"] == 2
    assert result.get("_malformed_json") is True
    assert "_raw_response_text" in result
    assert isinstance(result.get("extraction_notes"), list)


def test_extract_node_processes_files_concurrently(monkeypatch):
    class _FakeJob:
        current_stage = None

    class _FakeJobFile:
        def __init__(self, path: str):
            self.job_id = "job-concurrent"
            self.file_path = path
            self.extraction_status = None
            self.carrier_code = None
            self.lob_code = None
            self.policy_period_start = None
            self.policy_period_end = None

    class _FakeOutput:
        claims_json = None

    class _FakeQuery:
        def __init__(self, target):
            self.target = target

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            if self.target is extract_module.Job:
                return fake_job
            if self.target is extract_module.JobOutput:
                return fake_output
            if self.target is extract_module.JobFile:
                item = fake_files[_FakeQuery.job_file_first_index % len(fake_files)]
                _FakeQuery.job_file_first_index += 1
                return item
            return None

        def all(self):
            if self.target is extract_module.JobFile:
                return fake_files
            return []

    _FakeQuery.job_file_first_index = 0

    class _FakeSession:
        def query(self, target):
            return _FakeQuery(target)

        def commit(self):
            return None

        def close(self):
            return None

    fake_job = _FakeJob()
    fake_output = _FakeOutput()
    fake_files = [_FakeJobFile("file-a.pdf"), _FakeJobFile("file-b.pdf"), _FakeJobFile("file-c.pdf")]

    async def _fake_extract_one(file_path: str, client) -> dict:
        await asyncio.sleep(0.05)
        return {
            "_source_file": file_path,
            "carrier_code": "TEST",
            "carrier_name": "TEST",
            "lob": "GL",
            "policy_period_start": "2024-01-01",
            "policy_period_end": "2025-01-01",
        }

    monkeypatch.setattr(extract_module, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(extract_module, "_extract_one", _fake_extract_one)
    monkeypatch.setattr(extract_module, "get_gemini_client", lambda: object())

    started = monotonic()
    result = asyncio.run(
        extract_module.extract_node(
            {
                "job_id": "job-concurrent",
                "file_paths": [f.file_path for f in fake_files],
                "errors": [],
            }
        )
    )
    elapsed = monotonic() - started

    assert elapsed < 0.12
    assert len(result["raw_extractions"]) == 3
    assert all(f.extraction_status == extract_module.ExtractionStatus.completed for f in fake_files)
