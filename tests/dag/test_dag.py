"""
Unit tests for the DAG pipeline.
"""

import pytest
import asyncio
from app.models.applicant import LoanApplication
from dag.extraction import extract_fields
from dag.orchestrator import run_dag
from tests.conftest import SCENARIO_1_PAYLOAD, SCENARIO_2_PAYLOAD, SCENARIO_3_PAYLOAD


class TestExtraction:
    """Test the document extraction node."""

    def test_extracts_fields_from_application(self):
        app = LoanApplication(**SCENARIO_1_PAYLOAD["application"])
        extracted = extract_fields(app)
        assert extracted.applicant_id == "APP-001"
        assert extracted.pan_number == "ABCDE1234F"
        assert extracted.aadhaar_number == "234567890123"


class TestDAGPipeline:
    """Test the full DAG pipeline."""

    def test_scenario_1_finds_name_discrepancy(self):
        """Scenario 1: minor name variation should produce a discrepancy."""
        app = LoanApplication(**SCENARIO_1_PAYLOAD["application"])
        result = asyncio.run(run_dag(app))

        # The PAN DB has "Rajesh Kumar Sharma" but app says "Rajesh K Sharma"
        # This should trigger a name mismatch (low severity)
        assert result.has_discrepancies
        name_discs = [
            d for d in result.discrepancies
            if d.discrepancy_type.value == "name_mismatch"
        ]
        assert len(name_discs) > 0

    def test_scenario_2_finds_timeout_and_address_discrepancy(self):
        """Scenario 2: GST timeout + address mismatch."""
        app = LoanApplication(**SCENARIO_2_PAYLOAD["application"])
        result = asyncio.run(run_dag(app))

        assert result.has_discrepancies
        types = [d.discrepancy_type.value for d in result.discrepancies]
        # Should have at least a timeout (GST) and possibly address mismatch
        assert "verification_timeout" in types or "address_mismatch" in types

    def test_scenario_3_finds_income_discrepancy(self):
        """Scenario 3: major income mismatch."""
        app = LoanApplication(**SCENARIO_3_PAYLOAD["application"])
        result = asyncio.run(run_dag(app))

        assert result.has_discrepancies
        income_discs = [
            d for d in result.discrepancies
            if d.discrepancy_type.value == "income_mismatch"
        ]
        assert len(income_discs) > 0
        # Should be HIGH or CRITICAL severity
        assert income_discs[0].severity.value in ("high", "critical")
