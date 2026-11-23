import os
import sys
import unittest
from unittest import mock

# Ensure google.genai can be mocked if not installed in the test environment
if "google" not in sys.modules:
    mock_google = mock.MagicMock()
    mock_genai = mock.MagicMock()
    mock_google.genai = mock_genai
    sys.modules["google"] = mock_google
    sys.modules["google.genai"] = mock_genai
    sys.modules["google.genai.errors"] = mock.MagicMock()
    sys.modules["google.genai.types"] = mock.MagicMock()

# Add script directory to sys.path to import check_readme_drift
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".github", "scripts")))
import check_readme_drift


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


if __name__ == "__main__":
    unittest.main()
