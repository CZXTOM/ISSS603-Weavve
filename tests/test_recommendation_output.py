"""Publication-boundary checks use temporary synthetic files only."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_recommendations.py"
spec = importlib.util.spec_from_file_location("recommendation_cli", SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class PrivateOutputTests(unittest.TestCase):
    def test_rejects_repository_and_worktree_even_for_nonexistent_child(self):
        for worktree in (False, True):
            with self.subTest(worktree=worktree), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                if worktree:
                    (root / ".git").write_text("gitdir: synthetic-placeholder", encoding="utf-8")
                else:
                    (root / ".git").mkdir()
                with self.assertRaises(ValueError):
                    cli.private_output_directory(root / "new" / "output")

    def test_writes_valid_private_json_and_rejects_nonfinite_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = cli.write_report({"checks": {"dataset_id": "synthetic"}}, temporary)
            self.assertTrue(destination.exists())
            with self.assertRaises(ValueError):
                cli.write_report({"checks": {"dataset_id": "synthetic"}, "bad": float("nan")}, temporary)

    def test_rejects_redirected_output_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            repo.mkdir()
            (repo / ".git").mkdir()
            target = repo / "private.json"
            target.write_text("unchanged", encoding="utf-8")
            output = root / "private"
            output.mkdir()
            try:
                (output / "recommendation_checks.json").symlink_to(target)
            except OSError as exc:
                self.skipTest(f"Host cannot create file symlinks: {exc}")
            with self.assertRaises(ValueError):
                cli.write_report({"checks": {"dataset_id": "synthetic"}}, output)
            self.assertEqual(target.read_text(encoding="utf-8"), "unchanged")


if __name__ == "__main__":
    unittest.main()
