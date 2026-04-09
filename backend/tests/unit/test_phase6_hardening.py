from __future__ import annotations

from pathlib import Path
from time import monotonic
from time import sleep
import uuid

from app.pipeline.nodes import analytics as analytics_module
from app.pipeline.nodes import extract as extract_module
from app.pipeline.nodes import summary as summary_module
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

    def _fake_generate_structured_response(*, contents, response_schema):
        calls["count"] += 1
        return _Resp('{"broken_json":')

    monkeypatch.setattr(client, "_generate_structured_response", _fake_generate_structured_response)

    result = client.extract_claims(
        file_ref={"name": "fake"},
        prompt="extract",
        response_schema={},
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

    def _fake_extract_one(file_path: str, client) -> dict:
        sleep(0.05)
        return {
            "_source_file": file_path,
            "carrier_code": "TEST",
            "carrier_name": "TEST",
            "lob": "GL",
            "policy_period_start": "2024-01-01",
            "policy_period_end": "2025-01-01",
        }

    monkeypatch.setattr(extract_module, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(extract_module, "_extract_one", lambda file_path: _fake_extract_one(file_path, object()))
    monkeypatch.setattr(extract_module.settings, "GEMINI_MAX_CONCURRENT_REQUESTS", 8)

    started = monotonic()
    result = extract_module.extract_node(
        {
            "job_id": "job-concurrent",
            "file_paths": [f.file_path for f in fake_files],
            "errors": [],
        }
    )
    elapsed = monotonic() - started

    assert elapsed < 0.12
    assert len(result["raw_extractions"]) == 3
    assert all(f.extraction_status == extract_module.ExtractionStatus.completed for f in fake_files)


def test_extract_node_sets_quota_specific_error_message(monkeypatch):
    class _FakeJob:
        current_stage = None
        error_message = None

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
                return fake_file
            return None

        def all(self):
            if self.target is extract_module.JobFile:
                return [fake_file]
            return []

    class _FakeSession:
        def query(self, target):
            return _FakeQuery(target)

        def commit(self):
            return None

        def close(self):
            return None

    class _QuotaError(Exception):
        pass

    fake_job = _FakeJob()
    fake_output = type("Output", (), {"claims_json": None})()
    fake_file = type(
        "JobFile",
        (),
        {
            "job_id": "job-quota",
            "file_path": "file-a.pdf",
            "extraction_status": None,
            "carrier_code": None,
            "lob_code": None,
            "policy_period_start": None,
            "policy_period_end": None,
        },
    )()

    monkeypatch.setattr(extract_module, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(extract_module.settings, "GEMINI_MAX_CONCURRENT_REQUESTS", 1)
    monkeypatch.setattr(
        extract_module,
        "_extract_one",
        lambda file_path: (_ for _ in ()).throw(
            _QuotaError("429 RESOURCE_EXHAUSTED. Quota exceeded for metric")
        ),
    )

    try:
        extract_module.extract_node(
            {"job_id": "job-quota", "file_paths": ["file-a.pdf"], "errors": []}
        )
        assert False, "Expected extract_node to raise when all files fail"
    except RuntimeError as exc:
        assert "Gemini quota exceeded" in str(exc)
        assert "GEMINI_MOCK_MODE" in str(exc)
        assert "quota exceeded" in fake_job.error_message.lower()


def test_summary_node_falls_back_when_text_generation_fails(monkeypatch):
    class _FakeClient:
        def generate_text(self, prompt: str, context: str = "") -> str:
            raise RuntimeError("429 RESOURCE_EXHAUSTED. Quota exceeded for metric")

    class _FakeOutput:
        draft_summary = None
        redflags_json = None

    class _FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return fake_output

    class _FakeSession:
        def query(self, *args, **kwargs):
            return _FakeQuery()

        def commit(self):
            return None

        def close(self):
            return None

    fake_output = _FakeOutput()

    monkeypatch.setattr(summary_module, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(summary_module, "get_gemini_client", lambda: _FakeClient())
    monkeypatch.setattr(summary_module.settings, "GEMINI_MAX_CONCURRENT_REQUESTS", 1)

    result = summary_module.summary_node(
        {
            "job_id": "job-summary",
            "insured_name": "Test Insured",
            "claims_array": {
                "policy_periods": [
                    {
                        "claims": [
                            {"amount_incurred": "30000", "status": "open"},
                            {"amount_incurred": "1000", "status": "closed"},
                        ]
                    }
                ]
            },
            "analytics": {"years_analyzed": [2024], "yearly_stats": [], "overall_loss_ratio": 0.2},
            "red_flags": {"flags": [{"flag_type": "large_loss", "rule_description": "Large loss flag"}]},
        }
    )

    assert result["current_stage"] == "summary"
    assert "Test Insured" in result["draft_summary"]
    assert "Large loss flag" in result["red_flags"]["flags"][0]["narrative"]
