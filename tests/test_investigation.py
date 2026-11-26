import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from release_triage.main import app


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        path = Path(__file__).resolve().parents[1] / "release_triage/web/example-incident.json"
        sample = json.loads(path.read_text(encoding="utf-8"))
        self.payload = {"scenario": "upload", "alert": sample["alert"], "evidence": sample["records"]}

    def test_custom_bundle_reaches_same_agent(self):
        response = self.client.post("/api/investigate", json=self.payload)
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["category"], "release_timeout")
        self.assertEqual(set(report["citations"]), {row["id"] for row in self.payload["evidence"]})
        self.assertTrue(all(step["arguments"] == {"start": "00:00", "end": "23:59"} for step in report["trace"]))

    def test_bundle_rejects_invalid_schema_or_duplicate_ids(self):
        items = self.payload["evidence"]
        for records in (
            [items[0], items[0]],
            [dict(items[0], at="27:00")],
            [dict(items[0], source="logs")],
            [dict(items[0], current=None)],
        ):
            with self.subTest(records=records):
                response = self.client.post("/api/investigate", json=dict(self.payload, evidence=records))
                self.assertEqual(response.status_code, 422)

    def test_missing_conflicting_or_late_evidence_is_inconclusive(self):
        release, log, metric = self.payload["evidence"]
        for records in (
            [release, log],
            [release, log, metric, dict(metric, id="metric-conflict", current=1200)],
            [dict(release, at="12:08"), log, metric],
        ):
            with self.subTest(records=records):
                report = self.client.post("/api/investigate", json=dict(self.payload, evidence=records)).json()
                self.assertEqual(report["category"], "insufficient")

    def test_model_time_window_filters_sqlite_results(self):
        older = dict(self.payload["evidence"][2], id="outside-window", at="11:30")
        self.payload["evidence"].append(older)
        actions = iter((
            ("metrics", {"start": "12:05", "end": "12:10"}),
            ("logs", {}),
            ("releases", {}),
        ))

        def model_response(*_, **kwargs):
            name, args = next(actions)
            self.assertIn(name, [tool["function"]["name"] for tool in kwargs["json"]["tools"]])
            self.assertEqual(kwargs["json"]["model"], os.getenv("BAILIAN_MODEL", "kimi-k3"))
            self.assertNotIn("temperature", kwargs["json"])
            self.assertEqual(kwargs["timeout"], 60)
            return ToolResponse(name, args)

        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "mock-key"}):
            with patch("release_triage.agent.httpx.post", side_effect=model_response):
                response = self.client.post("/api/investigate", json=dict(self.payload, mode="bailian"))
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["category"], "release_timeout")
        self.assertNotIn("outside-window", {row["id"] for row in report["evidence"]})
        self.assertEqual(report["trace"][0]["arguments"], {"start": "12:05", "end": "12:10"})

    def test_bad_tool_arguments_fall_back_without_executing_them(self):
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "mock-key"}):
            with patch("release_triage.agent.httpx.post", return_value=ToolResponse("releases", {"start": "99:21"})):
                response = self.client.post("/api/investigate", json=dict(self.payload, mode="bailian"))
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["category"], "release_timeout")
        self.assertTrue(all(step["fallback"] and step["planner"] == "本地策略" for step in report["trace"]))


class ToolResponse:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments

    def raise_for_status(self):
        return None

    def json(self):
        function = {"name": self.name, "arguments": json.dumps(self.arguments)}
        return {"choices": [{"message": {"tool_calls": [{"function": function}]}}]}


if __name__ == "__main__":
    unittest.main()
