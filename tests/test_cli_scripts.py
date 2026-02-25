from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run_py(script_name: str, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPTS / script_name), *args]
    return subprocess.run(
        cmd,
        input=stdin,
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )


def run_sh(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = ["bash", str(SCRIPTS / script_name), *args]
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )


class ScriptHelpTests(unittest.TestCase):
    def test_refresh_openapi_help(self) -> None:
        proc = run_sh("refresh_openapi_snapshot.sh", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Usage: scripts/refresh_openapi_snapshot.sh", proc.stdout)

    def test_python_scripts_help(self) -> None:
        for script in (
            "validate_search_payload.py",
            "validate_extract_payload.py",
            "validate_task_payload.py",
            "verify_webhook_signature.py",
            "smoke_search.py",
            "smoke_extract.py",
            "smoke_task_run.py",
        ):
            with self.subTest(script=script):
                proc = run_py(script, "--help")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("usage:", proc.stdout.lower())


class SearchValidatorTests(unittest.TestCase):
    def test_validate_search_payload_valid(self) -> None:
        payload = {
            "mode": "one-shot",
            "objective": "Find 2025 SEC guidance on AI disclosures",
            "source_policy": {"include_domains": ["sec.gov"], "after_date": "2025-01-01"},
            "excerpts": {"max_chars_per_result": 1500, "max_chars_total": 5000},
        }
        proc = run_py("validate_search_payload.py", "-", stdin=json.dumps(payload))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK", proc.stdout)

    def test_validate_search_payload_invalid_domain(self) -> None:
        payload = {
            "search_queries": [],
            "source_policy": {"include_domains": ["https://bad.example/path"]},
        }
        proc = run_py("validate_search_payload.py", "-", stdin=json.dumps(payload))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("ERROR", proc.stdout)
        self.assertIn("include_domains[0]", proc.stdout)


class ExtractValidatorTests(unittest.TestCase):
    def test_validate_extract_payload_valid(self) -> None:
        payload = {
            "urls": ["https://www.example.com"],
            "objective": "Find pricing statements",
            "excerpts": {"max_chars_per_result": 1500, "max_chars_total": 3000},
            "full_content": {"max_chars_per_result": 8000},
        }
        proc = run_py(
            "validate_extract_payload.py",
            "--beta",
            "search-extract-2025-10-10",
            "-",
            stdin=json.dumps(payload),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK", proc.stdout)

    def test_validate_extract_payload_invalid_url(self) -> None:
        payload = {"urls": ["example.com"], "excerpts": False, "full_content": False}
        proc = run_py("validate_extract_payload.py", "-", stdin=json.dumps(payload))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("ERROR", proc.stdout)
        self.assertIn("$.urls[0]", proc.stdout)


class TaskValidatorTests(unittest.TestCase):
    def test_validate_task_payload_valid(self) -> None:
        payload = {
            "processor": "base",
            "input": {"country": "France", "year": 2023},
            "enable_events": True,
            "task_spec": {
                "output_schema": {
                    "type": "json",
                    "json_schema": {
                        "type": "object",
                        "properties": {"gdp": {"type": "string"}},
                        "required": ["gdp"],
                        "additionalProperties": False,
                    },
                }
            },
        }
        proc = run_py(
            "validate_task_payload.py",
            "--beta",
            "events-sse-2025-07-24",
            "-",
            stdin=json.dumps(payload),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK", proc.stdout)

    def test_validate_task_payload_warns_without_beta(self) -> None:
        payload = {"processor": "base", "input": "hello", "webhook": {"url": "https://example.com/webhook"}}
        proc = run_py("validate_task_payload.py", "-", stdin=json.dumps(payload))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("WARN", proc.stdout)
        self.assertIn("webhook is beta-gated", proc.stdout)


class WebhookVerifierTests(unittest.TestCase):
    def _signed_case(self) -> tuple[str, str, str, bytes, str]:
        secret = "sekret"
        webhook_id = "wh_123"
        timestamp = str(int(time.time()))
        body = b'{"run_id":"trun_test"}'
        signed = f"{webhook_id}.{timestamp}.".encode("utf-8") + body
        sig = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
        return secret, webhook_id, timestamp, body, sig

    def test_verify_webhook_signature_valid(self) -> None:
        secret, webhook_id, timestamp, body, sig = self._signed_case()
        with tempfile.TemporaryDirectory() as td:
            body_path = Path(td) / "body.json"
            body_path.write_bytes(body)
            proc = run_py(
                "verify_webhook_signature.py",
                "--secret",
                secret,
                "--webhook-id",
                webhook_id,
                "--timestamp",
                timestamp,
                "--signature-header",
                f"v1,{sig}",
                "--body-file",
                str(body_path),
                "--print-json",
            )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        parsed = json.loads(proc.stdout)
        self.assertTrue(parsed["valid"])
        self.assertTrue(parsed["matched_signature"])

    def test_verify_webhook_signature_replay_window_failure(self) -> None:
        secret = "sekret"
        webhook_id = "wh_123"
        timestamp = "1700000000"
        body = b"{}"
        signed = f"{webhook_id}.{timestamp}.".encode("utf-8") + body
        sig = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
        with tempfile.TemporaryDirectory() as td:
            body_path = Path(td) / "body.json"
            body_path.write_bytes(body)
            proc = run_py(
                "verify_webhook_signature.py",
                "--secret",
                secret,
                "--webhook-id",
                webhook_id,
                "--timestamp",
                timestamp,
                "--signature-header",
                f"v1,{sig}",
                "--body-file",
                str(body_path),
                "--now",
                str(int(timestamp) + 10_000),
                "--print-json",
            )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        parsed = json.loads(proc.stdout)
        self.assertFalse(parsed["valid"])
        self.assertFalse(parsed["within_tolerance"])


class SmokeSkipTests(unittest.TestCase):
    def test_smoke_scripts_skip_without_api_key(self) -> None:
        for script in ("smoke_search.py", "smoke_extract.py", "smoke_task_run.py"):
            with self.subTest(script=script):
                proc = run_py(script, "--api-key", "")
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertIn("SKIPPED", proc.stdout)


if __name__ == "__main__":
    unittest.main()
