"""HTTP protocol tests use an ephemeral loopback server and no external services."""

from __future__ import annotations

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ml.http_service import create_server


REQUEST = {
    "schemaVersion": 1,
    "feed_items": [{
        "id": "FEED-1",
        "text": "Severe yard congestion at Port of Mombasa causes 10-day dwell times for refrigerated pharma cargo.",
    }],
    "cargo_value": 450000,
    "incident_id": "SAP-8842",
}
TEST_TOKEN = "test-only-evaluator-token-0123456789abcdef"


class EvaluatorHttpServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(port=0, token=TEST_TOKEN)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def post(self, payload, token=TEST_TOKEN):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(
            self.base_url + "/internal/v1/evaluate",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            try:
                return error.code, json.loads(error.read())
            finally:
                error.close()

    def get(self, path):
        with urlopen(self.base_url + path, timeout=3) as response:
            return response.status, json.loads(response.read())

    def test_success_returns_evaluator_result_unchanged(self):
        status, body = self.post(REQUEST)
        self.assertEqual(status, 200)
        self.assertEqual(body["incident_id"], "SAP-8842")
        self.assertEqual(body["status"], "AWAITING_APPROVAL")
        self.assertEqual(body["classified_signals"][0]["category"], "PORT")
        self.assertEqual(body["decision_optimization"]["recommended_scenario_key"], "OPTION_C_SPLIT")

    def test_missing_and_invalid_credentials_are_rejected_before_evaluation(self):
        status, body = self.post(REQUEST, token=None)
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")

        status, body = self.post(REQUEST, token="invalid-token-value-0123456789abcdef")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")

    def test_server_refuses_to_start_without_a_configured_secret(self):
        for token in ("", "too-short", "x" * 32 + "\n"):
            with self.subTest(token_length=len(token)):
                with self.assertRaisesRegex(ValueError, "AEGISCHAIN_EVALUATOR_TOKEN"):
                    create_server(port=0, token=token)

    def test_invalid_json_and_schema_return_structured_client_errors(self):
        status, body = self.post(b'{"schemaVersion":')
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "invalid_request")
        self.assertNotIn("traceback", str(body).lower())

        status, body = self.post({**REQUEST, "schemaVersion": 2})
        self.assertEqual(status, 400)
        self.assertIn("schemaVersion", body["error"]["message"])

    def test_invalid_cargo_and_malformed_feed_return_structured_errors(self):
        status, body = self.post({**REQUEST, "cargo_value": -1})
        self.assertEqual(status, 422)
        self.assertEqual(body["error"]["code"], "invalid_evaluation_input")
        self.assertIn("cargo_value", body["error"]["message"])

        status, body = self.post({**REQUEST, "feed_items": [None]})
        self.assertEqual(status, 422)
        self.assertIn("feed_items[0]", body["error"]["message"])

    def test_health_and_readiness_endpoints(self):
        self.assertEqual(self.get("/healthz"), (200, {"status": "ok"}))
        self.assertEqual(self.get("/readyz"), (200, {"status": "ready"}))

    def test_unexpected_evaluator_error_does_not_expose_exception_details(self):
        def fail_evaluation(*_args, **_kwargs):
            raise RuntimeError("private-token stack details")

        server = create_server(port=0, evaluate=fail_evaluation, token=TEST_TOKEN)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_address[1]}/internal/v1/evaluate"
        request = Request(
            endpoint,
            data=json.dumps(REQUEST).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {TEST_TOKEN}"},
            method="POST",
        )
        try:
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=3)
            response = caught.exception
            try:
                body = json.loads(response.read())
            finally:
                response.close()
            self.assertEqual(response.code, 500)
            self.assertEqual(body["error"]["code"], "evaluation_failed")
            self.assertNotIn("private-token", json.dumps(body))
            self.assertNotIn("traceback", json.dumps(body).lower())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
