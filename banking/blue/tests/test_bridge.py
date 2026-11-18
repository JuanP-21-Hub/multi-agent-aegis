import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from dashboard.domain import groups, read_data
from run_blue import main


class IntegrationTests(unittest.TestCase):
    def test_audit_to_dashboard_with_mock_model(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            audit = root / "audit.jsonl"
            input_events = [
                {"path": "/api/accounts/983/transactions", "method": "GET", "status": 200,
                 "auth_role": "CUSTOMER", "required_role": "ACCOUNT_OWNER",
                 "authz_decision": "allowed", "authorization": "secret-fixture"},
                {"path": "/api/auth/customer/login", "method": "POST", "status": 401},
            ]
            audit.write_text("".join(json.dumps(event) + "\n" for event in input_events), encoding="utf-8")

            answer = {
                "classification": "suspicious", "severity": "medium",
                "summary": "<script>fixture</script>", "evidence_ids": ["E1"],
                "recommended_actions": ["근거를 검토하세요."], "limitations": "독립 검증 대기",
            }

            def model_call(base, path, payload=None, token=None, timeout=None):
                if path == "/models":
                    return {"data": [{"id": "openai/gpt-oss-20b"}]}
                self.assertEqual(path, "/chat/completions")
                content = payload["messages"][1]["content"]
                self.assertNotIn("secret-fixture", content)
                self.assertEqual(json.loads(content)["server_events"][0]["path"],
                                 "/api/accounts/{account_id}/transactions")
                return {"choices": [{"message": {"content": json.dumps(answer)}}]}

            runs = root / "runs"
            args = ["--log", str(audit), "--runs", str(runs), "--html"]
            with patch.dict("os.environ", {"FINLAB_BLUE_BASE_URL": "https://example.invalid/v1"}):
                with patch("blue_client.json_request", side_effect=model_call):
                    self.assertEqual(main(args), 0)
                    report = read_data(next(runs.glob("*/evaluation.json")))
                    self.assertEqual(report["analysis_status"], "completed")
                    self.assertEqual(report["logs"][0]["required_role"], "ACCOUNT_OWNER")
                    html = next(runs.glob("*/report_*.html")).read_text(encoding="utf-8")
                    self.assertIn("&lt;script&gt;fixture&lt;/script&gt;", html)
                    self.assertIn("권한 검사", html)
                    self.assertNotIn("secret-fixture", html)
                    self.assertEqual(report["blue_assessments"][0]["classification"], "suspicious")
                    baseline, blue, _, _ = groups(report)
                    self.assertEqual(baseline[0]["evidence_log_ids"], ["E2"])
                    self.assertEqual(blue[0]["evidence_log_ids"], ["E1"])
                    self.assertEqual(blue[0]["validation"], "pending")

                    answer["evidence_ids"] = ["made-up"]
                    self.assertEqual(main(args), 1)
                    reports = [read_data(p) for p in runs.glob("*/evaluation.json")]
                    failed = next(r for r in reports if r["analysis_status"] == "failed")
                    self.assertEqual(len(groups(failed)[0]), 1)
                    self.assertFalse(groups(failed)[1])

            self.assertEqual(main([*args, "--baseline-only"]), 0)
            self.assertEqual({read_data(p)["analysis_status"] for p in runs.glob("*/evaluation.json")},
                             {"completed", "failed", "pending"})
