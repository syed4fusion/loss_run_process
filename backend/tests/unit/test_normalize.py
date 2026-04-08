from app.pipeline.nodes import normalize as normalize_module


class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


class _FakeSession:
    def query(self, *args, **kwargs):
        return _FakeQuery()

    def commit(self):
        return None

    def close(self):
        return None


def _patch_db(monkeypatch):
    monkeypatch.setattr(normalize_module, "SessionLocal", lambda: _FakeSession())


def test_date_format_normalization_for_known_formats():
    expected = "2023-01-01"
    date_values = [
        "2023-01-01",
        "01/01/2023",
        "01/01/23",
        "01-Jan-23",
        "01-Jan-2023",
        "01-01-2023",
        "01-01-23",
        "Jan 01, 2023",
        "January 01, 2023",
    ]
    for value in date_values:
        parsed = normalize_module._parse_date(value)
        assert parsed is not None
        assert parsed.isoformat() == expected


def test_litigation_flag_matches_all_keywords():
    for keyword in normalize_module.LITIGATION_KEYWORDS:
        assert normalize_module._has_litigation(f"claim mentions {keyword} in notes")


def test_amount_incurred_reconciliation_adds_extraction_note(monkeypatch):
    _patch_db(monkeypatch)
    state = {
        "job_id": "j-normalize",
        "insured_name": "Test Insured",
        "raw_extractions": [
            {
                "carrier_name": "ABC Carrier",
                "carrier_code": "ABC",
                "lob": "cpkg",
                "policy_period_start": "2024-01-01",
                "policy_period_end": "2025-01-01",
                "earned_premium": "100000",
                "claims": [
                    {
                        "claim_number": "CLM-1",
                        "occurrence_date": "01/10/2024",
                        "close_date": "",
                        "status": "open",
                        "claim_type": "injury",
                        "description": "regular incident",
                        "amount_paid": "100",
                        "amount_reserved": "100",
                        "amount_incurred": "500",
                    }
                ],
            }
        ],
        "errors": [],
    }
    result = normalize_module.normalize_node(state)
    notes = result["claims_array"]["extraction_notes"]
    assert any("Claim CLM-1" in note for note in notes)
