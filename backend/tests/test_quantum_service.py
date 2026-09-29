"""Focused tests for the quantum service's validation and response contract."""

from __future__ import annotations

import tempfile
import unittest
import importlib.util
from pathlib import Path
from unittest.mock import patch

from services import analysis_service, quantum_service


DATASET = {"rows": 4, "feature_count": 3, "feature_names": ["x", "y", "z"]}
PROBLEM = {"task_type": "Binary Classification"}


class QuantumServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "tiny.csv"
        self.path.write_text("x,y,z,target\n1,3,a,0\n2,1,b,1\n3,4,a,0\n4,2,c,1\n", encoding="utf-8")
        self.metadata = {"stored_path": str(self.path)}

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_problem_returns_quantum_contract(self) -> None:
        measured = {"status": "completed", "algorithm": "QAOA", "features": ["x", "y", "z"], "qubits": 3, "depth": 8, "gate_count": 12, "two_qubit_gate_ratio": 0.25, "execution_time_sec": 0.01, "iterations": 16, "shots": 1024, "objective_value": 1.2, "expected_objective_value": 1.3, "best_bitstring": "101", "best_bitstring_count": 20, "parameters": {"gamma": 0.2, "beta": 0.5}}
        with patch.object(quantum_service, "_execute", return_value=measured):
            result = quantum_service.run(DATASET, PROBLEM, "an_test", self.metadata)
        self.assertFalse(result["is_mock"])
        self.assertTrue(result["quantum_analysis_real"])
        self.assertEqual(result["data_source"], "real")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["qubits_required"], 3)
        self.assertIn("suitability", result)
        self.assertEqual(result["algorithm"], "QAOA")
        self.assertEqual(result["feasibility"], "Executed locally")
        self.assertEqual(result["circuit_complexity"]["depth"], 8)
        self.assertEqual(result["circuit_complexity"]["gate_count"], 12)
        self.assertEqual(result["circuit_complexity"]["two_qubit_gate_ratio"], 0.25)
        self.assertEqual(result["execution"]["execution_time_sec"], 0.01)
        self.assertEqual(result["execution"]["shots"], 1024)
        self.assertEqual(result["execution"]["best_bitstring"], "101")
        self.assertEqual(result["execution"]["objective_value"], 1.2)
        self.assertEqual(result["execution"]["expected_objective_value"], 1.3)

    def test_empty_input_fails_gracefully(self) -> None:
        self.path.write_text("x,y\n", encoding="utf-8")
        result = quantum_service.run(DATASET, PROBLEM, "an_test", self.metadata)
        self.assertEqual(result["status"], "not_run")
        self.assertIn("no data rows", result["error"].lower())

    def test_missing_data_fails_gracefully(self) -> None:
        result = quantum_service.run(DATASET, PROBLEM, "an_test", {})
        self.assertEqual(result["recommended_approach"], "Classical computing")
        self.assertFalse(result["quantum_analysis_real"])
        self.assertEqual(result["data_source"], "unavailable")
        self.assertIn("unavailable", result["error"].lower())

    def test_unsupported_problem_type_fails_gracefully(self) -> None:
        result = quantum_service.run(DATASET, {"task_type": "Image Generation"}, "an_test", self.metadata)
        self.assertEqual(result["status"], "not_run")
        self.assertIn("unsupported problem type", result["error"].lower())

    def test_qaoa_result_describes_a_partition_not_a_feature_subset(self) -> None:
        measured = {"status": "completed", "algorithm": "QAOA", "features": ["x", "y", "z"], "qubits": 3, "depth": 8, "gate_count": 12, "two_qubit_gate_ratio": 0.25, "execution_time_sec": 0.01, "iterations": 16, "shots": 1024, "objective_value": 1.2, "expected_objective_value": 1.3, "best_bitstring": "101", "best_partition_bitstring": "101", "best_bitstring_count": 20, "partition_interpretation": "QAOA partitions the reduced feature graph based on feature relationships. The result is an optimization signal for feature selection, not a replacement for classical predictive-model validation.", "parameters": {"gamma": 0.2, "beta": 0.5}}
        with patch.object(quantum_service, "_execute", return_value=measured):
            result = quantum_service.run(DATASET, PROBLEM, "an_test", self.metadata)
        execution = result["execution"]
        self.assertEqual(execution["best_partition_bitstring"], "101")
        self.assertIn("partitions the reduced feature graph", execution["partition_interpretation"])
        self.assertNotIn("final selected-feature subset", execution["partition_interpretation"])

    def test_pipeline_marks_real_quantum_analysis_with_mixed_response_data(self) -> None:
        measured = {"status": "completed", "algorithm": "QAOA", "features": ["x", "y", "z"], "qubits": 3, "depth": 8, "gate_count": 12, "two_qubit_gate_ratio": 0.25, "execution_time_sec": 0.01, "iterations": 16, "shots": 1024, "objective_value": 1.2, "expected_objective_value": 1.3, "best_bitstring": "101", "best_partition_bitstring": "101", "best_bitstring_count": 20, "partition_interpretation": "QAOA partitions the reduced feature graph based on feature relationships. The result is an optimization signal for feature selection, not a replacement for classical predictive-model validation.", "parameters": {"gamma": 0.2, "beta": 0.5}}
        metadata = {"file_id": "fl_test", "file_name": "tiny.csv", "file_size_bytes": self.path.stat().st_size, "file_type": "csv", "uploaded_at": "2026-01-01T00:00:00Z", "stored_path": str(self.path)}
        with patch.object(quantum_service, "_execute", return_value=measured):
            payload = analysis_service.run_pipeline(metadata, "Predict binary classification", "an_test")
        self.assertEqual(payload["data_source"], "mixed")
        self.assertTrue(payload["mock_data"])
        self.assertTrue(payload["quantum_analysis_real"])
        self.assertTrue(payload["quantum_analysis"]["quantum_analysis_real"])
        self.assertEqual(payload["quantum_analysis"]["data_source"], "real")

    def test_simulator_failure_fails_gracefully(self) -> None:
        with patch.object(quantum_service, "_execute", side_effect=RuntimeError("simulator offline")):
            result = quantum_service.run(DATASET, PROBLEM, "an_test", self.metadata)
        self.assertEqual(result["status"], "not_run")
        self.assertIn("simulator offline", result["error"])

    @unittest.skipUnless(importlib.util.find_spec("qiskit_aer"), "Qiskit Aer not installed")
    def test_real_qiskit_execution(self) -> None:
        result = quantum_service.run(DATASET, PROBLEM, "an_test", self.metadata)
        self.assertEqual(result["status"], "completed")
        self.assertGreater(result["execution"]["objective_value"], 0)
        self.assertEqual(result["execution"]["best_partition_bitstring"], result["execution"]["best_bitstring"])
        self.assertIn("optimization signal", result["execution"]["partition_interpretation"])


if __name__ == "__main__":
    unittest.main()
