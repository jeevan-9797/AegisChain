import json
import subprocess
import sys
import unittest
from pathlib import Path

from ml import run_incident_evaluation


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CLI_COMMAND = [sys.executable, "-m", "ml.cli"]
FEED_ITEMS = [
    {
        "id": "SIG-8842-01",
        "text": "Houthi missile barrage strikes a vessel off Bab el-Mandeb.",
    }
]


def make_request(**overrides):
    request = {
        "schemaVersion": 1,
        "feed_items": FEED_ITEMS,
        "cargo_value": 450000,
        "incident_id": "SAP-8842",
    }
    request.update(overrides)
    return request


def run_cli(stdin_text, *args):
    return subprocess.run(
        [*CLI_COMMAND, *args],
        input=stdin_text,
        text=True,
        capture_output=True,
        cwd=REPOSITORY_ROOT,
        timeout=30,
        check=False,
    )


class IncidentCliTests(unittest.TestCase):
    def test_valid_request_returns_existing_evaluator_json(self):
        request = make_request()
        completed = run_cli(json.dumps(request))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(completed.stdout.count("\n"), 1)
        response = json.loads(completed.stdout)
        expected = run_incident_evaluation(
            request["feed_items"],
            cargo_value=request["cargo_value"],
            incident_id=request["incident_id"],
        )

        for result in (response, expected):
            result.pop("timestamp")
            result["execution_metadata"].pop("latency_ms")
        self.assertEqual(response, expected)

    def test_missing_or_empty_stdin_is_rejected(self):
        for stdin_text in ("", " \n\t"):
            with self.subTest(stdin_text=repr(stdin_text)):
                completed = run_cli(stdin_text)
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(completed.stdout, "")
                self.assertIn("stdin must contain", completed.stderr)

    def test_invalid_json_is_rejected(self):
        completed = run_cli('{"schemaVersion":')
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("invalid JSON request", completed.stderr)

    def test_unsupported_schema_version_is_rejected(self):
        completed = run_cli(json.dumps(make_request(schemaVersion=2)))
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("schemaVersion must be the integer 1", completed.stderr)

    def test_missing_required_fields_are_rejected(self):
        completed = run_cli(json.dumps({"schemaVersion": 1}))
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("missing required field(s)", completed.stderr)

    def test_unknown_fields_including_cap_ids_are_rejected(self):
        completed = run_cli(json.dumps(make_request(shipment_ids=["not-a-python-field"])))
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("unsupported field(s): shipment_ids", completed.stderr)

    def test_invalid_cargo_value_fails_in_evaluator_without_success_json(self):
        completed = run_cli(json.dumps(make_request(cargo_value=-1)))
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertIn("evaluation error: ValueError", completed.stderr)
        self.assertIn("cargo_value must be a finite number greater than zero", completed.stderr)

    def test_malformed_feed_item_fails_in_evaluator_without_success_json(self):
        completed = run_cli(json.dumps(make_request(feed_items=[None])))
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertIn("evaluation error: ValueError", completed.stderr)
        self.assertIn("feed_items[0] must be a mapping", completed.stderr)

    def test_extra_json_value_after_request_is_rejected(self):
        completed = run_cli(json.dumps(make_request()) + " {}")
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("invalid JSON request", completed.stderr)

    def test_command_line_arguments_are_rejected(self):
        completed = run_cli(json.dumps(make_request()), "unexpected.json")
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("command-line arguments are not supported", completed.stderr)


if __name__ == "__main__":
    unittest.main()
