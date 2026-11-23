import os
import sys
import unittest
from unittest import mock

# Ensure google.genai can be mocked if not installed in the test environment
class FakeAPIError(Exception):
    def __init__(self, code: int, message: str = "API error"):
        super().__init__(message)
        self.code = code


if "google" not in sys.modules:
    mock_google = mock.MagicMock()
    mock_genai = mock.MagicMock()
    mock_google.genai = mock_genai
    sys.modules["google"] = mock_google
    sys.modules["google.genai"] = mock_genai
    mock_errors = mock.MagicMock()
    mock_errors.APIError = FakeAPIError
    sys.modules["google.genai.errors"] = mock_errors
    sys.modules["google.genai.types"] = mock.MagicMock()

# Add script directory to sys.path to import check_readme_drift
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".github", "scripts")))
import check_readme_drift

# Ensure check_readme_drift.errors.APIError is set to an exception class
if not isinstance(check_readme_drift.errors.APIError, type) or not issubclass(check_readme_drift.errors.APIError, BaseException):
    check_readme_drift.errors.APIError = FakeAPIError
APIError = check_readme_drift.errors.APIError


class TestCheckReadmeDrift(unittest.TestCase):
    @mock.patch("subprocess.run")
    def test_get_diff_excludes_readme(self, mock_run):
        mock_process = mock.MagicMock()
        mock_process.stdout = "diff --git a/foo.py b/foo.py\n..."
        mock_run.return_value = mock_process

        diff = check_readme_drift.get_diff("main")

        self.assertEqual(diff, "diff --git a/foo.py b/foo.py\n...")
        self.assertEqual(mock_run.call_count, 2)
        # Check fetch call
        fetch_call = mock_run.call_args_list[0]
        self.assertEqual(fetch_call[0][0], ["git", "fetch", "origin", "main"])
        # Check diff call
        diff_call = mock_run.call_args_list[1]
        diff_cmd = diff_call[0][0]
        self.assertIn(":(exclude)README.md", diff_cmd)
        self.assertIn(":(exclude,glob)**/go.sum", diff_cmd)

    def test_prompt_template_guidelines(self):
        prompt = check_readme_drift.PROMPT_TEMPLATE
        self.assertIn("excludes README.md", prompt)
        self.assertIn("PR author has already updated README.md", prompt)
        self.assertIn("NOT drift", prompt)

    def test_write_output(self):
        with mock.patch("builtins.print") as mock_print:
            temp_output = "/tmp/test_github_output.txt"
            if os.path.exists(temp_output):
                os.remove(temp_output)
            try:
                with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": temp_output}):
                    check_readme_drift.write_output(needs_update=True, reason="Identifier `foo` changed.")
                    with open(temp_output, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.assertIn("needs_update=true", content)
                    self.assertIn("Identifier `foo` changed.", content)
            finally:
                if os.path.exists(temp_output):
                    os.remove(temp_output)


class TestCallGemini(unittest.TestCase):
    def setUp(self):
        self.mock_client = mock.MagicMock()

    def test_call_gemini_success_first_try(self):
        mock_response = mock.MagicMock()
        mock_response.text = "NEEDS_UPDATE: no"
        self.mock_client.models.generate_content.return_value = mock_response

        with mock.patch("time.sleep") as mock_sleep:
            result = check_readme_drift.call_gemini(self.mock_client, "test prompt")

        self.assertEqual(result, "NEEDS_UPDATE: no")
        self.mock_client.models.generate_content.assert_called_once_with(
            model=check_readme_drift.MODEL_CHAIN[0], contents="test prompt"
        )
        mock_sleep.assert_not_called()

    def test_call_gemini_quota_exceeded_429_falls_back_immediately(self):
        mock_success_response = mock.MagicMock()
        mock_success_response.text = "NEEDS_UPDATE: no"

        self.mock_client.models.generate_content.side_effect = [
            APIError(code=429, message="Resource exhausted"),
            mock_success_response,
        ]

        with mock.patch("time.sleep") as mock_sleep, mock.patch("sys.stderr"):
            result = check_readme_drift.call_gemini(self.mock_client, "test prompt")

        self.assertEqual(result, "NEEDS_UPDATE: no")
        mock_sleep.assert_not_called()
        self.assertEqual(self.mock_client.models.generate_content.call_count, 2)
        # First call was model 0, second was model 1
        calls = self.mock_client.models.generate_content.call_args_list
        self.assertEqual(calls[0][1]["model"], check_readme_drift.MODEL_CHAIN[0])
        self.assertEqual(calls[1][1]["model"], check_readme_drift.MODEL_CHAIN[1])

    def test_call_gemini_503_backoff_and_retry_success(self):
        mock_success_response = mock.MagicMock()
        mock_success_response.text = "NEEDS_UPDATE: yes"

        self.mock_client.models.generate_content.side_effect = [
            APIError(code=503, message="Service unavailable"),
            mock_success_response,
        ]

        with mock.patch("time.sleep") as mock_sleep, mock.patch("sys.stderr"):
            result = check_readme_drift.call_gemini(self.mock_client, "test prompt")

        self.assertEqual(result, "NEEDS_UPDATE: yes")
        mock_sleep.assert_called_once_with(check_readme_drift.BACKOFF_SECONDS)
        self.assertEqual(self.mock_client.models.generate_content.call_count, 2)
        # Both calls were for model 0
        calls = self.mock_client.models.generate_content.call_args_list
        self.assertEqual(calls[0][1]["model"], check_readme_drift.MODEL_CHAIN[0])
        self.assertEqual(calls[1][1]["model"], check_readme_drift.MODEL_CHAIN[0])

    def test_call_gemini_503_continues_falls_back_to_next_model(self):
        mock_success_response = mock.MagicMock()
        mock_success_response.text = "NEEDS_UPDATE: no"

        self.mock_client.models.generate_content.side_effect = [
            APIError(code=503, message="503 try 1"),
            APIError(code=503, message="503 try 2"),
            mock_success_response,
        ]

        with mock.patch("time.sleep") as mock_sleep, mock.patch("sys.stderr"):
            result = check_readme_drift.call_gemini(self.mock_client, "test prompt")

        self.assertEqual(result, "NEEDS_UPDATE: no")
        mock_sleep.assert_called_once_with(check_readme_drift.BACKOFF_SECONDS)
        self.assertEqual(self.mock_client.models.generate_content.call_count, 3)
        calls = self.mock_client.models.generate_content.call_args_list
        self.assertEqual(calls[0][1]["model"], check_readme_drift.MODEL_CHAIN[0])
        self.assertEqual(calls[1][1]["model"], check_readme_drift.MODEL_CHAIN[0])
        self.assertEqual(calls[2][1]["model"], check_readme_drift.MODEL_CHAIN[1])

    def test_call_gemini_all_models_fail_graceful_none(self):
        # 3 models, each hitting 503 twice = 6 calls total
        self.mock_client.models.generate_content.side_effect = [
            APIError(code=503, message="503"),
            APIError(code=503, message="503"),
            APIError(code=503, message="503"),
            APIError(code=503, message="503"),
            APIError(code=503, message="503"),
            APIError(code=503, message="503"),
        ]

        with mock.patch("time.sleep") as mock_sleep, mock.patch("sys.stderr"):
            result = check_readme_drift.call_gemini(self.mock_client, "test prompt")

        self.assertIsNone(result)
        self.assertEqual(mock_sleep.call_count, 3)
        self.assertEqual(self.mock_client.models.generate_content.call_count, 6)

    def test_call_gemini_non_fallback_error_returns_none(self):
        self.mock_client.models.generate_content.side_effect = APIError(code=400, message="Bad request")

        with mock.patch("time.sleep") as mock_sleep, mock.patch("sys.stderr"):
            result = check_readme_drift.call_gemini(self.mock_client, "test prompt")

        self.assertIsNone(result)
        mock_sleep.assert_not_called()
        self.mock_client.models.generate_content.assert_called_once()

    def test_call_gemini_generic_exception_returns_none(self):
        self.mock_client.models.generate_content.side_effect = RuntimeError("Network error")

        with mock.patch("time.sleep") as mock_sleep, mock.patch("sys.stderr"):
            result = check_readme_drift.call_gemini(self.mock_client, "test prompt")

        self.assertIsNone(result)
        mock_sleep.assert_not_called()
        self.mock_client.models.generate_content.assert_called_once()


if __name__ == "__main__":
    unittest.main()
